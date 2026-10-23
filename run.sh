#!/usr/bin/env bash
# Lance ZakhrafaAI : installe les dépendances (si besoin) puis démarre le serveur.
set -e
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "Création de l'environnement virtuel..."
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "ZakhrafaAI démarre sur http://127.0.0.1:8000"
echo "Ouvrez cette adresse dans votre navigateur."
echo ""
# ajoutez --reload pour le développement
uvicorn app.main:app --host 127.0.0.1 --port 8000
