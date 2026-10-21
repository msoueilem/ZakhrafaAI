@echo off
cd /d "%~dp0backend"

if not exist ".venv" (
  echo Creation de l'environnement virtuel...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo.
echo ZakhrafaAI demarre sur http://localhost:8000
echo Ouvrez cette adresse dans votre navigateur.
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
