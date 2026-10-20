#!/usr/bin/env bash
# Sobe a PoC SEM Docker, usando a fila por arquivo (TRANSPORT=file).
# Uso: bash run_local.sh     (Linux/Mac/WSL)
set -e
cd "$(dirname "$0")"

python -m venv .venv 2>/dev/null || true
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt

export TRANSPORT=file
export EVENT_QUEUE_DIR="$PWD/event_queue"

echo "Subindo cashflow-service (8001) e consolidation-service (8002)..."
PORT=8001 python -m cashflow_service &
CF=$!
PORT=8002 python -m consolidation_service &
CONS=$!
trap "kill $CF $CONS 2>/dev/null || true" EXIT

sleep 3
echo "Pronto."
echo "  cashflow:       http://localhost:8001/docs"
echo "  consolidation:  http://localhost:8002/docs"
echo
echo "Exemplo:"
echo '  curl -X POST localhost:8001/entries -H "Content-Type: application/json" \'
echo '       -d "{\"merchant_id\":\"M1\",\"type\":\"CREDIT\",\"amount\":100,\"entry_date\":\"2026-10-20\"}"'
echo '  curl "localhost:8002/balance?merchant_id=M1&date=2026-10-20"'
wait
