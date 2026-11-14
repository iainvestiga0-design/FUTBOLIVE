@echo off
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
echo.
echo   En la compu:   http://localhost:8000
echo   En el celular: usa la direccion IPv4 que muestra "ipconfig" + :8000  (mismo Wi-Fi)
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8000
