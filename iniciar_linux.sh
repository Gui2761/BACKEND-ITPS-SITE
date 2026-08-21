#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
echo "========================================================"
echo "  INICIANDO BACKEND ITPS (FASTAPI) E TUNEL CLOUDFLARE   "
echo "========================================================"
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi
pip install -r requirements.txt --quiet
echo "[1/2] Iniciando FastAPI na porta 8000..."
nohup python3 main.py > backend.log 2>&1 &
sleep 3
if command -v cloudflared &> /dev/null; then
    echo "[2/2] Iniciando Cloudflare Tunnel com HTTP/2..."
    nohup cloudflared tunnel --protocol http2 --url http://localhost:8000 > tunnel.log 2>&1 &
    sleep 4
    echo "========================================================"
    echo "Túnel iniciado! Link gerado:"
    grep -o 'https://.*trycloudflare.com' tunnel.log
    echo "========================================================"
else
    echo "[AVISO] cloudflared não encontrado no sistema."
fi
