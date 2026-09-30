# GyanSys Agentic Migration Tool (MARC demo)

React + Vite (JavaScript) frontend, FastAPI + LangGraph (Python) backend, Azure OpenAI, SharePoint via Microsoft Graph.

## Run

Double-click `start.bat`, or start the two servers yourself:

```bash
backend/.venv/Scripts/python.exe -m uvicorn --app-dir backend app.main:app --port 8010 --reload --reload-dir backend/app
```

```bash
npm --prefix frontend run dev
```

Then open http://localhost:5180. The API docs are at http://localhost:8010/docs.
These ports (8010 and 5180) are used so the tool doesn't clash with other local projects on 8000 and 5173.

First-time setup: `python -m venv backend/.venv`, then `backend/.venv/Scripts/pip install -r backend/requirements.txt`, then `npm --prefix frontend install`. Copy `backend/.env.example` to `backend/.env` and fill it in, and put `MARC_MBEW_Mappings.xlsx` in `templates/` (neither is committed).

## Configuration: `backend/.env`

| Setting | Meaning |
|---|---|
| `SP_TENANT_ID`, `SP_CLIENT_ID`, `SP_CLIENT_SECRET`, `SP_HOSTNAME`, `SP_SITE_PATH` | Graph app registration and SharePoint site |
| `SP_MAPPINGS_FOLDER` | The folder the Rulebook's Fetch button opens (default `Mappings`) |
| `SP_DATABRICKS_FOLDER`, `SP_DATABRICKS_FILE` | The Databricks output used for validation (default `Databricks Files/S_MARC#FreeText - {plant}.csv`) |
| `VALIDATION_PLANT` | The plant that is validated (default `1021`) |
| `MATCH_PASS_MARK`, `FIELD_PASS_MARK` | The pass marks for "rows found" (0.95) and "key field values match" (0.99) |
| `SOURCE_MODE` | `sharepoint`, or `local` (`local_sharepoint/` is laid out like the library) |
| `LLM_PROVIDER`, `AZURE_OPENAI_*` | `azure`, or `none` (reads the rules without the model) |

## Flow

1. **Data Extraction:** select the MARC file in SharePoint to see a preview.
2. **Rulebook:** Fetch the mapping document, then Generate rulebook. The rulebook is shown in the template format; Approve and start begins processing.
3. **Agents:** Fetch data → Rulebook → Approve → Transform → Validate → Report.
4. **Reports:** the validation result for plant 1021 plus downloads (S/4 file, validation report, rulebook).

## Layout

```
backend/app/
  connectors/  sharepoint.py (Graph: list, download), source.py (browse, tables, documents, Parquet cache)
  llm/         azure.py
  rulebook/    parser.py (LLM + cross-check), writer.py (template Excel), service.py
  engine/      transform.py, validate.py (plant vs Databricks), outputs.py
  graph/       pipeline.py (LangGraph nodes and the approval step), runner.py (background runs, resume)
  store/       runs.py (run.json + events.jsonl)
  main.py      REST API + SSE stream
frontend/src/
  pages/       Extraction, Rulebook, Agents, Runs, Approvals, Reports
  components/  Layout, FilePicker, StatusStrip, Stepper, DecisionPanel, ValidationCard, DataTable, ui
```
