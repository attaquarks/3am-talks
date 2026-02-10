@echo off
REM 3AM Talks — Start both backend API (port 5050) and frontend dev server (port 5173)
REM Usage: start.bat
REM Prerequisites:
REM   - Python venv activated with deps installed (pip install -r requirements.txt)
REM   - Node.js deps installed (cd frontend && npm install)
REM   - Ollama running with psychocounsel model (ollama run psychocounsel)
REM   - .env configured with SUPABASE_URL, SUPABASE_KEY, PINECONE_API_KEY

echo ================================================
echo   3AM Talks (ELLA AI) — Starting Services
echo ================================================

echo [1/3] Starting backend API on http://localhost:5050 (using .venv) ...
start "3AM-Backend" cmd /c "cd /d %~dp0 && %~dp0.venv\Scripts\python.exe src\api.py"

echo [2/3] Starting frontend on http://localhost:5173 ...
start "3AM-Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo [3/3] Starting Voice Agent (Ella) ...
start "3AM-VoiceAgent" cmd /c "cd /d %~dp0 && %~dp0.venv\Scripts\python.exe src\voice_agent.py dev"

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
