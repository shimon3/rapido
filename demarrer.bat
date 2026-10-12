@echo off
REM Lance Rapido et ouvre l'interface dans le navigateur
cd /d "%~dp0"
if not exist ".venv" (
    echo Premiere installation...
    python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)
start "" http://localhost:9614
.venv\Scripts\python app.py
