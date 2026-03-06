#!/usr/bin/env bash
# Start SirHENRY API + Frontend for local development.
# Usage: ./dev.sh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $API_PID $FRONTEND_PID 2>/dev/null || true
    wait $API_PID $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}Done.${NC}"
}
trap cleanup EXIT INT TERM

# ── Python venv ──────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3.12 -m venv .venv
fi

if [ ! -f ".venv/lib/python3.12/site-packages/fastapi/__init__.py" ]; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    .venv/bin/pip install -q -r requirements.txt
fi

# ── Node modules ─────────────────────────────────────────────
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    (cd frontend && npm install)
fi

# ── .env check ───────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo -e "${RED}Missing .env file. Copy .env.example and fill in your keys.${NC}"
    exit 1
fi

# ── Start API ────────────────────────────────────────────────
echo -e "${GREEN}Starting API server (http://localhost:8000)...${NC}"
.venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 &
API_PID=$!

# ── Start Frontend ───────────────────────────────────────────
echo -e "${GREEN}Starting frontend (http://localhost:3000)...${NC}"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

# ── Wait ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}SirHENRY is running:${NC}"
echo "  API:      http://localhost:8000"
echo "  Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both."
wait
