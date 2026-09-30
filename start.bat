@echo off
rem Starts the FastAPI backend (port 8010) and the Vite frontend (port 5180).
cd /d "%~dp0"
start "Agentic backend" cmd /k "backend\.venv\Scripts\python.exe -m uvicorn --app-dir backend app.main:app --port 8010 --reload --reload-dir backend\app"
start "Agentic frontend" cmd /k "npm --prefix frontend run dev"
timeout /t 4 >nul
start http://localhost:5180
