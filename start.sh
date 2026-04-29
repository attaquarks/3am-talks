#!/usr/bin/env bash
# Ella Speaks Calmly — Start backend (5050), ngrok tunnel for Vercel,
# voice agent, and the local frontend dev server.
# Usage: ./start.sh
#
# Prerequisites:
#   - Python venv at .venv with deps installed (pip install -r requirements.txt)
#   - Node.js deps installed (cd frontend && npm install) — only needed if you
#     want to iterate on UI locally; the Vercel build is the production frontend
#   - .env configured (SUPABASE_*, PINECONE_*, LIVEKIT_*, ELEVEN_*, ngrok-free)
#   - ngrok CLI installed and authenticated (ngrok config add-authtoken ...)
#   - LLM reachable at LLM_PRIMARY_URL (GPU PC on LAN, or localhost Ollama)
#   - LiveKit Cloud (LIVEKIT_URL in .env) — no local LiveKit server needed

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
NGROK_DOMAIN="noncoagulative-crissy-unsuffocative.ngrok-free.dev"

echo "================================================"
echo "  Ella Speaks Calmly — Starting Services"
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

echo "[1/4] Starting backend API on http://localhost:5050 ..."
open_terminal "Ella-Backend" "source .venv/bin/activate && python src/main.py"

echo "[2/4] Starting ngrok tunnel → ${NGROK_DOMAIN} (port 5050) ..."
open_terminal "Ella-Ngrok" "ngrok http --domain=${NGROK_DOMAIN} 5050"

echo "[3/4] Starting Voice Agent (Ella) ..."
open_terminal "Ella-VoiceAgent" "source .venv/bin/activate && python src/voice/agent.py dev"

echo "[4/4] Starting local frontend dev server on http://localhost:5173 (optional) ..."
open_terminal "Ella-Frontend" "cd frontend && npm run dev"

echo
echo "================================================"
echo "  All services starting in separate Terminal windows!"
echo "  Backend API:        http://localhost:5050"
echo "  ngrok inspector:    http://127.0.0.1:4040"
echo "  Public backend URL: https://${NGROK_DOMAIN}"
echo "  Vercel frontend:    https://ella-speaks-calmly.vercel.app"
echo "  Local frontend:     http://localhost:5173 (dev only)"
echo "  Voice Agent:        Ella-VoiceAgent window"
echo "================================================"
echo "  Close each Terminal window to stop that service"
echo "================================================"
