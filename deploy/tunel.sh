#!/usr/bin/env bash
# Túnel reverso: a VM (porta 8001 local dela) passa a alcançar o servidor desta máquina (porta 8000).
# Reconecta sozinho se cair. Uso: deploy/tunel.sh <ip-da-vm> <chave-privada>
VM="${1:?informe o IP da VM}"; CHAVE="${2:?informe a chave privada}"
cd "$(dirname "$0")/.." || exit 1
mkdir -p logs
pgrep -f "ssh .*-R 127.0.0.1:8001:127.0.0.1:8000" >/dev/null && { echo "túnel já ativo"; exit 0; }
setsid nohup bash -c "while true; do
  ssh -i '$CHAVE' -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
      -R 127.0.0.1:8001:127.0.0.1:8000 ubuntu@$VM
  echo \"\$(date) túnel caiu; reconectando em 5 s\"; sleep 5
done" > logs/tunel.log 2>&1 < /dev/null &
echo "túnel iniciado (log: logs/tunel.log)"
