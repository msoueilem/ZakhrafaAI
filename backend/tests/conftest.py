"""Fixtures partagées : client HTTP de test et historique remis à zéro."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture()
def client():
    main._HISTORY.clear()
    with TestClient(main.app) as c:
        yield c
    main._HISTORY.clear()
