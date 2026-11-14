#!/usr/bin/env bash
# Arranca FUTBOLIVE en tu computadora y muestra la dirección para abrir desde el celular.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo ""; echo "  En la compu:   http://localhost:8000"
[ -n "$IP" ] && echo "  En el celular: http://$IP:8000   (mismo Wi-Fi)"; echo ""
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
