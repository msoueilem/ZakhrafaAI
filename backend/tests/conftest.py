"""Fixtures partagées : client HTTP de test, historique remis à zéro et
rendu IA isolé (pas de clé, compteur dans un dossier temporaire)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main
from app.services import deepseek, gemini


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


@pytest.fixture(autouse=True)
def isolated_deepseek(tmp_path, monkeypatch):
    """Aucun test ne doit appeler le vrai DeepSeek ni lire une clé du shell."""
    for var in ("DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_DAILY_LIMIT",
                "DEEPSEEK_PER_IP_LIMIT", "DEEPSEEK_TIMEOUT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("ZAKHRAFAAI_DATA_DIR", str(tmp_path / "data"))
    deepseek.reset_assistant()
    yield
    deepseek.reset_assistant()


@pytest.fixture()
def client():
    main.reset_stats()
    with TestClient(main.app) as c:
        yield c
    main.reset_stats()
