#!/usr/bin/env bash
# Ella Speaks Calmly - Run backend + ngrok tunnel + voice agent for the Vercel-deployed frontend
# Usage: ./vercel.sh
# Prerequisites:
#   - .venv created with deps installed (pip install -r requirements.txt)
#   - ngrok installed and authtoken configured (ngrok config add-authtoken ...)
#   - .env configured with FRONTEND_URL=https://frontend-ten-rho-38.vercel.app
#   - Friend's LLM reachable via COLAB_API_URL in .env
# Frontend: https://frontend-ten-rho-38.vercel.app (served by Vercel; do NOT start vite here)

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================================"
echo "  Ella Speaks Calmly - Vercel-mode services"
echo "================================================"

open_terminal() {
  local title="$1"
  local cmd="$2"
  osascript \
    -e "tell application \"Terminal\"" \
    -e "activate" \
    -e "do script \"cd '${PROJECT_DIR}' && printf '\\\\e]0;${title}\\\\a' && ${cmd}\"" \
    -e "end tell" >/dev/null
}

echo "[1/3] Starting backend API on http://localhost:5050 (using .venv) ..."
open_terminal "Ella-Backend" "source .venv/bin/activate && python -m uvicorn src.main:app --host 0.0.0.0 --port 5050 --reload"

echo "[2/3] Starting ngrok tunnel on earache-procurer-console.ngrok-free.dev ..."
open_terminal "Ella-Ngrok" "ngrok http --domain=earache-procurer-console.ngrok-free.dev 5050"

echo "[3/3] Starting Voice Agent (Ella) ..."
open_terminal "Ella-VoiceAgent" "source .venv/bin/activate && python src/voice/agent.py dev"

echo
echo "================================================"
echo "  All services starting in separate Terminal windows!"
echo "  Site:          https://frontend-ten-rho-38.vercel.app"
echo "  Backend:       http://localhost:5050 (local)"
echo "  Public tunnel: https://earache-procurer-console.ngrok-free.dev"
echo "  Health check:  https://earache-procurer-console.ngrok-free.dev/api/health"
echo "================================================"
echo "  Close the Terminal windows to stop services"
echo "================================================"
