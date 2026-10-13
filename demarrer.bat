@echo off
REM Lance Rapido depuis le code source (pour developper).
REM Pour une utilisation normale, installe plutot Rapido-Setup.exe depuis la page Releases.
cd /d "%~dp0"
if not exist ".venv" (
    echo Premiere installation...
    python -m venv .venv
    .venv\Scripts\python -m pip install -q -r requirements.txt
)
start "" .venv\Scripts\pythonw desktop.py
