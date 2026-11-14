#!/usr/bin/env bash
# Sobe a aplicação completa nesta máquina (porta 8000), em segundo plano.
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
pgrep -f "uvicorn webapp.servidor:app" >/dev/null && { echo "já está rodando"; exit 0; }
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True setsid nohup .venv/bin/python -m uvicorn webapp.servidor:app \
  --host 127.0.0.1 --port 8000 > logs/servidor.log 2>&1 < /dev/null &
echo "servidor iniciado (log: logs/servidor.log)"
