"""Fixtures partagées : client HTTP de test, historique remis à zéro et
rendu IA isolé (pas de clé, compteur dans un dossier temporaire)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import gemini


@pytest.fixture(autouse=True)
def isolated_gemini(tmp_path, monkeypatch):
    """Aucun test ne doit appeler le vrai Gemini ni lire une clé du shell."""
    for var in ("GEMINI_API_KEY", "GEMINI_IMAGE_MODEL", "GEMINI_DAILY_LIMIT",
                "GEMINI_PER_IP_LIMIT", "GEMINI_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ZAKHRAFAAI_DATA_DIR", str(tmp_path / "data"))
    gemini.reset_renderer()
    yield
    gemini.reset_renderer()


@pytest.fixture()
def client():
    main._HISTORY.clear()
    with TestClient(main.app) as c:
        yield c
    main._HISTORY.clear()
