"""
Azure OpenAI chat client (adapted from Sharepoint-RO-Automation's gateway).
GPT-5 deployments are reasoning models: no temperature, output capped with
max_completion_tokens, reasoning_effort sent when the API version accepts it.
"""
from __future__ import annotations

import json
import time

from openai import AzureOpenAI, BadRequestError

from app.config import settings


class LLMNotConfigured(RuntimeError):
    pass


_client: AzureOpenAI | None = None
_optional = {"reasoning_effort": True, "response_format": True}


def available() -> bool:
    return settings.llm_configured


def _get() -> AzureOpenAI:
    global _client
    if not settings.llm_configured:
        raise LLMNotConfigured("Azure OpenAI is not configured (AZURE_OPENAI_* in backend/.env, LLM_PROVIDER=azure).")
    if _client is None:
        _client = AzureOpenAI(api_key=settings.AZURE_OPENAI_API_KEY,
                              azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                              api_version=settings.AZURE_OPENAI_API_VERSION,
                              timeout=300, max_retries=2)
    return _client


def chat(messages: list[dict], *, json_mode: bool = False, max_tokens: int | None = None) -> dict:
    """Returns {"text", "usage", "model", "seconds"}."""
    kwargs: dict = {"model": settings.AZURE_OPENAI_CHAT_DEPLOYMENT, "messages": messages,
                    "max_completion_tokens": max_tokens or settings.LLM_MAX_OUTPUT_TOKENS}
    if settings.LLM_REASONING_EFFORT and _optional["reasoning_effort"]:
        kwargs["reasoning_effort"] = settings.LLM_REASONING_EFFORT
    if json_mode and _optional["response_format"]:
        kwargs["response_format"] = {"type": "json_object"}

    started = time.time()
    for _ in range(3):
        try:
            resp = _get().chat.completions.create(**kwargs)
            break
        except BadRequestError as exc:
            dropped = False
            for opt in ("reasoning_effort", "response_format"):
                if opt in kwargs and opt in str(exc):
                    _optional[opt] = False
                    kwargs.pop(opt)
                    dropped = True
            if not dropped:
                raise
    else:
        raise RuntimeError("Azure OpenAI rejected the request")

    u = resp.usage
    return {"text": resp.choices[0].message.content or "",
            "usage": {"prompt": getattr(u, "prompt_tokens", 0), "completion": getattr(u, "completion_tokens", 0),
                      "total": getattr(u, "total_tokens", 0)} if u else {},
            "model": settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            "seconds": round(time.time() - started, 1)}


def chat_json(system: str, user: str) -> tuple[dict, dict]:
    out = chat([{"role": "system", "content": system}, {"role": "user", "content": user}], json_mode=True)
    text = out["text"].strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    return json.loads(text), out
