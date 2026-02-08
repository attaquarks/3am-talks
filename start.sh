#!/usr/bin/env bash
# 3AM Talks — Start both backend API (port 5050) and frontend dev server (port 5173)
# Usage: ./start.sh
# Prerequisites:
#   - Python venv activated with deps installed (pip install -r requirements.txt)
#   - Node.js deps installed (cd frontend && npm install)
#   - Ollama running with psychocounsel model (ollama run psychocounsel)
#   - .env configured with SUPABASE_URL, SUPABASE_KEY, PINECONE_API_KEY

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "================================================"
echo "  3AM Talks (ELLA AI) — Starting Services"
echo "================================================"

# Start backend API
echo "[1/2] Starting backend API on http://localhost:5050 ..."
cd "$ROOT_DIR/src"
python api.py &
BACKEND_PID=$!
echo "       Backend PID: $BACKEND_PID"

# Start frontend dev server
echo "[2/2] Starting frontend on http://localhost:5173 ..."
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo "       Frontend PID: $FRONTEND_PID"

echo ""
echo "================================================"
echo "  Both services running!"
echo "  Backend API:  http://localhost:5050"
echo "  Frontend:     http://localhost:5173"
echo "  Health check: http://localhost:5050/api/health"
echo "================================================"
echo "  Press Ctrl+C to stop both services"
echo "================================================"

# Trap Ctrl+C to kill both processes
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo "All services stopped."
}
trap cleanup SIGINT SIGTERM

# Wait for either process to exit
wait
