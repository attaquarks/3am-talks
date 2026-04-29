@echo off
REM Ella Speaks Calmly - Run backend + ngrok tunnel + voice agent for the Vercel-deployed frontend
REM Usage: vercel.bat
REM Prerequisites:
REM   - .venv activated with deps installed (pip install -r requirements.txt)
REM   - ngrok installed and authtoken configured (ngrok config add-authtoken ...)
REM   - .env configured with FRONTEND_URL=https://ella-speaks-calmly.vercel.app
REM   - LLM reachable at LLM_PRIMARY_URL (GPU PC on LAN, or localhost Ollama)
REM     COLAB_API_URL kept as a fallback if the primary is down
REM Frontend: https://ella-speaks-calmly.vercel.app (served by Vercel; do NOT start vite here)

echo ================================================
echo   Ella Speaks Calmly - Vercel-mode services
echo ================================================

echo [1/3] Starting backend API on http://localhost:5050 (using .venv) ...
start "Ella-Backend" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" -m uvicorn src.main:app --host 0.0.0.0 --port 5050 --reload"

echo [2/3] Starting ngrok tunnel on noncoagulative-crissy-unsuffocative.ngrok-free.dev ...
start "Ella-Ngrok" cmd /k "ngrok http --domain=noncoagulative-crissy-unsuffocative.ngrok-free.dev 5050"

echo [3/3] Starting Voice Agent (Ella) ...
start "Ella-VoiceAgent" cmd /k "cd /d "%~dp0" && ".venv\Scripts\python.exe" src\voice\agent.py dev"

echo.
echo ================================================
echo   All services starting in separate windows!
echo   Site:          https://ella-speaks-calmly.vercel.app
echo   Backend:       http://localhost:5050 (local)
echo   Public tunnel: https://noncoagulative-crissy-unsuffocative.ngrok-free.dev
echo   Health check:  https://noncoagulative-crissy-unsuffocative.ngrok-free.dev/api/health
echo ================================================
echo   Close the terminal windows to stop services
echo ================================================
pause
