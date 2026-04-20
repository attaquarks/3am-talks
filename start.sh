#!/usr/bin/env bash
# 3AM Talks — Start backend API (5050), frontend dev server (5173), and voice agent
# Usage: ./start.sh
# Prerequisites:
#   - Python venv at .venv with deps installed (pip install -r requirements.txt)
#   - Node.js deps installed (cd frontend && npm install)
#   - .env configured with SUPABASE_URL, SUPABASE_KEY, PINECONE_API_KEY, COLAB_API_URL
#   - LiveKit server running (livekit-server) for the voice agent

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================================"
echo "  3AM Talks (ELLA AI) — Starting Services"
echo "================================================"

open_terminal() {
  local title="$1"
  local cmd="$2"
  osascript \
    -e "tell application \"Terminal\"" \
    -e "activate" \
    -e "do script \"cd '${ROOT_DIR}' && printf '\\\\e]0;${title}\\\\a' && ${cmd}\"" \
    -e "end tell" >/dev/null
}

echo "[1/3] Starting backend API on http://localhost:5050 ..."
open_terminal "Ella-Backend" "source .venv/bin/activate && python src/main.py"

echo "[2/3] Starting frontend on http://localhost:5173 ..."
open_terminal "Ella-Frontend" "cd frontend && npm run dev"

echo "[3/3] Starting Voice Agent (Ella) ..."
open_terminal "Ella-VoiceAgent" "source .venv/bin/activate && python src/voice/agent.py dev"

echo
echo "================================================"
echo "  All services starting in separate Terminal windows!"
echo "  Backend API:  http://localhost:5050"
echo "  Frontend:     http://localhost:5173"
echo "  Voice Agent:  Ella-VoiceAgent window"
echo "  Health check: http://localhost:5050/api/health"
echo "================================================"
echo "  Close each Terminal window to stop that service"
echo "================================================"
