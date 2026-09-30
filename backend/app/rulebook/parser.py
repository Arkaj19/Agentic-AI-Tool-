"""
Plain-English plant rules -> structured rules.

The Rulebook agent (Azure OpenAI) reads the document and returns JSON in a
fixed schema. The result is validated, and cross-checked against a
deterministic reader of the same text; any disagreement is reported so a
person sees it before approving (G1). With LLM_PROVIDER=none the
deterministic reader is used on its own.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.llm import azure

PLANT_RE = re.compile(r"\b(1\d{3})\b")
TARGET_RE = re.compile(r"\b([A-Z]{2}\d{2})\b")


class PlantRules(BaseModel):
    object: str = "MARC"
    field: str = "WERKS"
    splits: dict[str, list[str]] = Field(default_factory=dict)
    one_to_one: dict[str, str] = Field(default_factory=dict)
    unmapped_policy: Literal["keep_and_flag", "exclude"] = "keep_and_flag"
    checks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("splits")
    @classmethod
    def _splits(cls, v: dict[str, list[str]]) -> dict[str, list[str]]:
        out = {}
        for plant, targets in v.items():
            t = [str(x).strip().upper() for x in targets if str(x).strip()]
            if len(t) < 2:
                raise ValueError(f"split plant {plant} needs at least two target plants, got {t}")
            if len(set(t)) != len(t):
                raise ValueError(f"split plant {plant} lists a target twice: {t}")
            out[str(plant).strip()] = t
        return out

    @field_validator("one_to_one")
    @classmethod
    def _one(cls, v: dict[str, str]) -> dict[str, str]:
        return {str(k).strip(): str(t).strip().upper() for k, t in v.items()}

    def all_plants(self) -> set[str]:
        return set(self.splits) | set(self.one_to_one)

    def targets_for(self, plant: str) -> list[str] | None:
        if plant in self.splits:
            return self.splits[plant]
        if plant in self.one_to_one:
            return [self.one_to_one[plant]]
        return None


CHECK_IDS = ["split_count_x2", "one_to_one_count", "traceability", "split_coverage", "werks_not_blank"]

SYSTEM_PROMPT = f"""You are the Rulebook agent of an SAP ECC -> S/4HANA data-migration tool.
You read a plain-English mapping document for table MARC and extract ONLY the plant (WERKS) rules:
which ECC plant (4 digits, e.g. 1021) becomes which S/4 plant(s) (e.g. US27). Lines that only describe groups
of S/4 plants (e.g. "DC plants -> US30, US31") are context, not plant rules.

Return a single JSON object with exactly these keys:
- "object": "MARC"
- "field": "WERKS"
- "splits": object mapping each ECC plant that becomes several S/4 plants to the list of S/4 plants, in the order written. Example: {{"1021": ["US27", "US30"]}}
- "one_to_one": object mapping each ECC plant that becomes exactly one S/4 plant to that plant. Example: {{"1025": "US29"}}
- "unmapped_policy": "keep_and_flag" if rows of plants without a rule are kept with their ECC value and flagged, "exclude" if they are dropped.
- "checks": list of validation checks the document asks for, using only these ids: {CHECK_IDS}
- "notes": short list of anything in the document you could not express in this schema (empty list if none).

Rules:
- Use plant codes exactly as written (strings). Do not invent plants or targets that are not in the document.
- A plant must not appear in both "splits" and "one_to_one".
- Output JSON only, no commentary."""


def deterministic(text: str) -> PlantRules:
    """Reads plant -> target mentions line by line. Used as a cross-check and
    as the parser when no LLM is configured."""
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        plants = PLANT_RE.findall(line)
        targets = TARGET_RE.findall(line.upper())
        if len(set(plants)) != 1 or not targets:
            continue
        lst = found.setdefault(plants[0], [])
        for t in targets:
            if t not in lst:
                lst.append(t)
    splits = {p: t for p, t in found.items() if len(t) > 1}
    one = {p: t[0] for p, t in found.items() if len(t) == 1}
    low = text.lower()
    policy = "exclude" if ("drop" in low and "unmapped" not in low) else "keep_and_flag"
    checks = []
    if re.search(r"2\s*[x×]", low):
        checks.append("split_count_x2")
    if "equal" in low:
        checks.append("one_to_one_count")
    if "trace" in low:
        checks.append("traceability")
    if "both" in low:
        checks.append("split_coverage")
    if "never be blank" in low or "not be blank" in low:
        checks.append("werks_not_blank")
    return PlantRules(splits=splits, one_to_one=one, unmapped_policy=policy, checks=checks or CHECK_IDS)


def compare(a: PlantRules, b: PlantRules) -> list[str]:
    diffs = []
    for plant in sorted(a.all_plants() | b.all_plants()):
        ta, tb = a.targets_for(plant), b.targets_for(plant)
        if ta != tb:
            diffs.append(f"Plant {plant}: agent says {ta or 'no rule'}, text scan says {tb or 'no rule'}")
    return diffs


def parse(text: str, *, use_llm: bool = True) -> dict:
    """Returns {"rules": PlantRules, "parser", "crosscheck", "llm"}."""
    det = deterministic(text)
    if not (use_llm and azure.available()):
        return {"rules": det, "parser": "deterministic", "llm": None,
                "crosscheck": {"agree": True, "diffs": [], "note": "LLM not configured; text scan used"}}

    last_err = None
    for attempt in range(2):
        user = f"Rule document:\n\n{text}"
        if last_err:
            user += f"\n\nYour previous answer was invalid: {last_err}. Return corrected JSON."
        try:
            data, meta = azure.chat_json(SYSTEM_PROMPT, user)
            rules = PlantRules.model_validate(data)
            overlap = set(rules.splits) & set(rules.one_to_one)
            if overlap:
                raise ValueError(f"plants in both splits and one_to_one: {sorted(overlap)}")
            rules.checks = [c for c in rules.checks if c in CHECK_IDS] or CHECK_IDS
            diffs = compare(rules, det)
            return {"rules": rules, "parser": "azure-openai",
                    "llm": {"model": meta["model"], "seconds": meta["seconds"], "usage": meta["usage"],
                            "attempts": attempt + 1},
                    "crosscheck": {"agree": not diffs, "diffs": diffs}}
        except azure.LLMNotConfigured:
            break
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {str(exc)[:300]}"
    raise RuntimeError(f"Rulebook agent could not produce valid rules: {last_err}")
