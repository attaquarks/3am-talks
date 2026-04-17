@echo off
REM 3AM Talks — Start both backend API (port 5050) and frontend dev server (port 5173)
REM Usage: start.bat
REM Prerequisites:
REM   - Python venv activated with deps installed (pip install -r requirements.txt)
REM   - Node.js deps installed (cd frontend && npm install)
REM   - .env configured with SUPABASE_URL, SUPABASE_KEY, PINECONE_API_KEY, COLAB_API_URL

echo ================================================
echo   3AM Talks (ELLA AI) — Starting Services
echo ================================================

echo [1/3] Starting backend API on http://localhost:5050 (using .venv) ...
REM Use -m uvicorn so the app loads once as src.api (avoids odd reload/double-import with python src\api.py)
REM Close the old "3AM-Backend" window before re-running start.bat, or you keep a stale API (wrong routes / HTTP 404).
start "3AM-Backend" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" -m uvicorn src.api:app --host 0.0.0.0 --port 5050 --reload"

echo [2/3] Starting frontend on http://localhost:5173 ...
start "3AM-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo [3/3] Starting Voice Agent (Ella) ...
start "3AM-VoiceAgent" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" src\voice_agent.py dev"

echo.
echo ================================================
echo   All services starting in separate windows!
echo   Backend API:  http://localhost:5050
echo   Frontend:     http://localhost:5173
echo   Voice Agent:  Running (LiveKit Cloud)
echo   Health check: http://localhost:5050/api/health
echo ================================================
echo   Close the terminal windows to stop services
echo ================================================
pause
