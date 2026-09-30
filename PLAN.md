# Agentic Migration Tool: Build Plan

**Frontend:** React + Vite (JavaScript) · **Backend:** Python (FastAPI + LangGraph) · **LLM:** Azure OpenAI · **Data:** SharePoint via Microsoft Graph
**Scope for now:** MARC only (plant data, S_MARC)

---

## 1. What already exists and will be reused

`AgenticAISharepointTool/Sharepoint-RO-Automation` already has working code that I will **copy in and reuse** instead of rewriting:

| Existing module | Reused for |
|---|---|
| `connectors/sharepoint.py` (MSAL client-credentials, Graph list, download, retry on 429/503) | Data Extraction: fetching ECC files from SharePoint. Upload will be added so reports and S/4 files can be written back (you have Graph read/write access). |
| `agents/llm/azure_openai.py` + `core/config.py` (the same `SP_*` / `AZURE_OPENAI_*` env variables) | The Rulebook and Remediation agents. The same `.env` layout lets you reuse your existing values. |
| `reference_logic/sap_labels.yaml` | Converting ECC's descriptive headers ("Plant", "Procurement type"…) into SAP field names (WERKS, BESKZ…) |
| `ingest/readers.py` | Reading the `.XLSX` extracts |

**Real data profile** (current snapshot, `MARC_DAP 8.10.26.XLSX`): **29,387 rows, 251 columns, 13 plants.**

| Plant | Rows | Rule |
|---|---|---|
| 1021 | 14,482 | split → US27 + US30 |
| 1028 | 7,314 | split → US28 + US30 |
| 1025 | 3,593 | → US29 |
| 1030 | 1,734 | split → US32 + US33 |
| 1029 | 655 | → CA02 |
| 1035, 1055, 1033, 1031, 1032, 1034, 1041, 1000 | 1,609 in total | **no rule → unmapped** |

This means the approval gate (G2) will fire naturally on real data: 8 plants with no rule.

> ⚠ The real S/4 output in the existing project contains **US31** (4,231 rows), which suggests that plant 1028 → US28 + **US31** in production. As agreed, the rules follow the screenshot (US28 + US30). The reconciliation step will point this out if we compare against the real S/4 file.

## 2. Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18 + Vite (JavaScript / JSX), Tailwind CSS, React Router |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Agent framework | **LangGraph (Python)**: `StateGraph`, `interrupt()` at approval gates, and a checkpointer (`SqliteSaver`) so paused runs survive a restart |
| LLM | Azure OpenAI (the existing gateway, or `AzureChatOpenAI` from `langchain-openai`) |
| SharePoint | Microsoft Graph (MSAL, client credentials): read the ECC files and rules document, write the reports and S/4 files |
| Data / Excel | pandas (transform), openpyxl (formatted Excel output) |
| Live progress | Server-Sent Events from FastAPI to the React `EventSource` |

## 3. Folder structure (inside `Agentic Tool/`)

```
Agentic Tool/
├─ PLAN.md
├─ start.bat                       # starts backend + frontend
├─ rules/
│  └─ MARC_Mapping_Rules.md        # plain-English rules (the Rulebook agent's input)
├─ templates/
│  └─ MARC_MBEW_Mappings.xlsx      # format template only (columns, layout, styling)
├─ backend/
│  ├─ requirements.txt
│  ├─ .env.example                 # SP_TENANT_ID, SP_CLIENT_ID, SP_CLIENT_SECRET, SP_HOSTNAME,
│  │                               # SP_SITE_PATH, SP_ECC_FOLDER_PATH, SP_RULES_PATH, SP_OUTPUT_FOLDER,
│  │                               # AZURE_OPENAI_ENDPOINT / API_KEY / API_VERSION / CHAT_DEPLOYMENT
│  └─ app/
│     ├─ main.py                   # FastAPI app + routes
│     ├─ config.py
│     ├─ connectors/sharepoint.py  # reused + upload_file()
│     ├─ llm/azure_openai.py       # reused
│     ├─ labels.py                 # descriptive header → SAP field (from sap_labels.yaml)
│     ├─ rulebook/
│     │  ├─ parser.py              # LLM: English rules → structured JSON (validated schema)
│     │  └─ writer.py              # JSON + hardcoded S_MARC fields → mapping Excel (template format)
│     ├─ engine/
│     │  ├─ transform.py           # applies plant rules (split / one-to-one / unmapped)
│     │  └─ validate.py            # checks 8–12 from the rules document
│     ├─ graph/
│     │  ├─ state.py
│     │  ├─ pipeline.py            # nodes + gates
│     │  └─ events.py              # SSE event bus
│     ├─ store/runs.py             # run history (JSON / SQLite)
│     └─ output/<run_id>/          # mapping.xlsx, S_MARC.xlsx, validation_report.xlsx
└─ frontend/
   ├─ package.json
   └─ src/
      ├─ api.js
      ├─ components/  Sidebar, Header, StatusCards, Stepper, AgentCard, DecisionPanel, DataTable, LogStream
      └─ pages/       Extraction, Runs, Rulebook, Approvals, Agents, Reports
```

## 4. How the rules become the mapping Excel

1. **Read** `MARC_Mapping_Rules.md` from SharePoint (with a local copy as fallback).
2. **LLM (Azure OpenAI) parses** the text into structured rules that are checked against a fixed schema:
   ```json
   {"object":"MARC","field":"WERKS",
    "splits":{"1021":["US27","US30"],"1028":["US28","US30"],"1030":["US32","US33"]},
    "one_to_one":{"1025":"US29","1029":"CA02"},
    "unmapped_policy":"keep_and_flag",
    "checks":["split_count_x2","one_to_one_count","traceability","split_coverage","werks_not_blank"]}
   ```
   If the LLM output doesn't match the schema, it is retried. If it still fails, the step stops with an error; the tool never silently makes a guess.
3. **Write the Excel** in the same 12-column layout as `MARC_MBEW_Mappings.xlsx` (Filters · Group · Field description · Mandatory · Type · Length · Decimals · Structure · Source table · Target field · Rule type · Rule logic):
   - The S_MARC field rows (PRODUCT, WERKS, DISMM, DISPO, MTVFP, MMSTA, MMSTD, KOKRS, PRCTR, AUSME…) are **hardcoded**, taken from the template's MARC sheet.
   - Only the **WERKS row's Rule logic** is generated from the parsed rules, in the same "For 1021: … → US27, US30" style.
4. The **preview** is shown in the Rulebook tab. **Approve & Run** is gate G1.

## 5. Tabs

| Tab | Purpose |
|---|---|
| **Data Extraction** | Connects to SharePoint and lists the ECC files (MARC for now). Shows a paged preview of the real extract, with a toggle between descriptive and SAP headers, and a profile: rows, plants, blanks, and whether each plant has a rule. |
| **Runs** | History of pipeline runs: run ID, rules version, status, ECC rows → S/4 rows, unmapped count, duration, gate decisions. Buttons open a run in Agents or Reports, and two runs can be compared. |
| **Rulebook** | Shows the plain-English rules, a **Generate mapping** button (runs the LLM), a preview of the generated Excel, a download button, and **Approve & Run**, which starts the pipeline and switches to Agents. |
| **Approvals** | Pending and past gate decisions (G1, G2), each with approve, edit or reject, a comment, who decided, and when. |
| **Agents** | Connection cards (SharePoint, Azure OpenAI), a step bar, agent cards (Queued / Running / Done / Needs approval), a live log for the step that's running, and the **Needs your decision** panel. Approving resumes the graph. |
| **Reports** | For each run: the validation report, the S_MARC load file and the mapping Excel. All can be downloaded, and each shows whether it was uploaded to SharePoint. |

## 6. LangGraph pipeline

```
Extract ─▶ Profile ─▶ Build mapping ─▶ ⏸ G1 approve mapping ─▶ Transform ─▶ Validate
   ─▶ ⏸ G2 remediation (only if unmapped/failed) ─▶ Generate S/4 file ─▶ Report ─▶ Publish to SharePoint
```

| Node | What it does |
|---|---|
| Extract | Downloads MARC from SharePoint and converts the headers to SAP names |
| Profile | Counts rows per plant and blanks, and finds plants that have no rule |
| Build mapping | Rulebook agent (LLM) → structured rules → mapping Excel |
| **G1** | `interrupt()`: the user approves the mapping |
| Transform | Splits or maps each row; rows with no rule are kept and flagged unmapped |
| Validate | Runs checks 8–12 from the rules document |
| **G2** | Only when there are unmapped plants or failed checks. The Remediation agent (LLM) proposes value maps per plant (e.g. `1035 → ?`). The user approves, edits or excludes each one; approved maps loop back to Transform. |
| Generate | Writes the S_MARC load file (approved rows only) |
| Report | Writes the validation report Excel (summary, checks, unmapped detail, row counts per plant) |
| Publish | Uploads the reports and S/4 file to the SharePoint output folder |

## 7. To-do list

1. Set up the project: `backend/` (FastAPI, requirements, `.env.example`), `frontend/` (Vite React JS + Tailwind), and `start.bat`.
2. Copy the reused modules in: SharePoint connector, Azure OpenAI gateway, config, SAP labels. Add `upload_file()` to the connector.
3. Backend: extraction API (`GET /api/sharepoint/status`, `/api/ecc/files`, `/api/ecc/{file}/preview`, `/api/ecc/{file}/profile`).
4. Backend: Rulebook agent (rules → JSON through the LLM, validated against the schema) and the Excel writer using the template format; endpoints to generate, preview and download.
5. Backend: LangGraph pipeline (state, nodes, G1 and G2 `interrupt()`, SQLite checkpointer, resume endpoint).
6. Backend: SSE progress stream (`GET /api/runs/{id}/events`).
7. Backend: transform engine (split, one-to-one, unmapped) and validation checks 8–12.
8. Backend: Remediation agent proposals for G2, the S_MARC file, the validation report, and publishing to SharePoint.
9. Backend: runs, approvals and reports API.
10. Frontend: app shell (sidebar, header, status cards, routing, API client).
11. Frontend: Data Extraction tab.
12. Frontend: Rulebook tab.
13. Frontend: Agents tab (stepper, agent cards, live log, decision panel, resume).
14. Frontend: Approvals, Runs and Reports tabs.
15. Test end to end on the real MARC extract. Check that the counts are right (1021 → 2 × 14,482, etc.) and that G2 fires for the 8 plants with no rule.

## 8. Needed from you before step 3

- Fill in `backend/.env` with the SharePoint and Azure OpenAI values (copy them from your existing project's `.env`; please don't paste them in chat).
- The SharePoint folder where the rules document should live, and the output folder for reports and S/4 files.
