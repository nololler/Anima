#!/usr/bin/env bash
# ─────────────────────────────────────────
#  Anima — startup script
# ─────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════╗"
echo "║         A N I M A           ║"
echo "╚══════════════════════════════╝"

# Backend
echo ""
echo "→ Starting backend..."
pip install -r requirements.txt -q
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Frontend
echo "→ Starting frontend..."
cd frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✓ Backend:  http://localhost:8000"
echo "✓ Frontend: http://localhost:5173"
echo "✓ API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both."

cleanup() {
  echo ""
  echo "Stopping Anima..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit 0
}

trap cleanup INT TERM
wait
