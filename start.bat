@echo off
REM Ella Speaks Calmly - Start backend (5050), ngrok tunnel for Vercel,
REM voice agent, and the local frontend dev server.
REM Usage: start.bat
REM
REM Prerequisites:
REM   - .venv with deps installed (pip install -r requirements.txt)
REM   - Node.js deps installed (run "npm install" in the frontend folder)
REM     - only needed if you want to iterate on UI locally
REM   - .env configured (SUPABASE_*, PINECONE_*, LIVEKIT_*, ELEVEN_*, ngrok-free)
REM   - ngrok CLI installed and authenticated (ngrok config add-authtoken ...)
REM   - LLM reachable at LLM_PRIMARY_URL (GPU PC on LAN, or localhost Ollama)
REM   - LiveKit Cloud (LIVEKIT_URL in .env) - no local LiveKit server needed

set NGROK_DOMAIN=noncoagulative-crissy-unsuffocative.ngrok-free.dev

echo ================================================
echo   Ella Speaks Calmly - Starting Services
echo ================================================

echo [1/4] Starting backend API on http://localhost:5050 (using .venv) ...
REM Use -m uvicorn so the app loads once as src.main (avoids odd reload/double-import with python src\main.py)
REM Close the old "Ella-Backend" window before re-running start.bat, or you keep a stale API (wrong routes / HTTP 404).
start "Ella-Backend" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" -m uvicorn src.main:app --host 0.0.0.0 --port 5050 --reload"

echo [2/4] Starting ngrok tunnel on %NGROK_DOMAIN% ...
start "Ella-Ngrok" cmd /k "ngrok http --domain=%NGROK_DOMAIN% 5050"

echo [3/4] Starting Voice Agent (Ella) ...
start "Ella-VoiceAgent" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" -m src.voice.agent dev"

echo [4/4] Starting local frontend dev server on http://localhost:5173 (optional) ...
start "Ella-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ================================================
echo   All services starting in separate windows!
echo   Backend API:        http://localhost:5050
echo   ngrok inspector:    http://127.0.0.1:4040
echo   Public backend URL: https://%NGROK_DOMAIN%
echo   Vercel frontend:    https://ella-speaks-calmly.vercel.app
echo   Local frontend:     http://localhost:5173 (dev only)
echo   Voice Agent:        Ella-VoiceAgent window
echo ================================================
echo   Close the terminal windows to stop services
echo ================================================
pause
