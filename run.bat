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
echo ZakhrafaAI demarre sur http://127.0.0.1:8000
echo Ouvrez cette adresse dans votre navigateur.
echo.
rem ajoutez --reload pour le developpement
uvicorn app.main:app --host 127.0.0.1 --port 8000
