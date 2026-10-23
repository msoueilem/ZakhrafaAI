"""Contrat « codes machine » consommé par le frontend trilingue (fr/ar/en) :
notice_code/notice_params de /api/generate, 422 avec code + fields,
compteurs cumulés et vignettes du tableau de bord, meta.assist."""
from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

from app import main

from .test_assist import FAKE_KEY as DS_KEY
from .test_assist import enable as enable_assist  # noqa: F401 (fixture)
from .test_gemini import (FAKE_KEY, _blocked, _garbage, _http_500, _no_image, _timeout, ai,
                          enable)  # noqa: F401 (fixture)


def gen(client, **payload):
    body = {"category": "zellige", "engine": "gan", "palette": "fes_bleu", **payload}
    return client.post("/api/generate", json=body)


# --- notice_code / notice_params ---------------------------------------------

def test_success_has_null_code_and_empty_params(client, enable):
    enable()
    data = ai(client).json()
    assert data["source"] == "gemini"
    assert data["notice"] is None and data["notice_code"] is None and data["notice_params"] == {}


def test_fast_mode_has_null_code(client):
    data = gen(client, seed=1).json()
    assert data["notice_code"] is None and data["notice_params"] == {}


def test_code_ai_disabled(client):
    data = ai(client).json()
    assert (data["notice_code"], data["notice_params"]) == ("ai_disabled", {})
    assert data["notice"]  # message français conservé


def test_code_daily_limit_with_param(client, enable):
    enable(daily_limit=1, per_ip_limit=100)
    assert ai(client, seed=1).json()["notice_code"] is None
    data = ai(client, seed=2).json()
    assert (data["notice_code"], data["notice_params"]) == ("daily_limit", {"n": 1})
    assert "Quota journalier" in data["notice"]


def test_code_ip_limit_with_param(client, enable):
    enable(_http_500, per_ip_limit=1)
    ai(client, seed=1)
    data = ai(client, seed=2).json()
    assert (data["notice_code"], data["notice_params"]) == ("ip_limit", {"n": 1})


@pytest.mark.parametrize("responder, code", [
    (_timeout, "timeout"),
    (_no_image, "blocked"),
    (_blocked, "blocked"),
    (_http_500, "service_error"),
    (_garbage, "service_error"),
])
def test_code_per_gemini_failure(client, enable, responder, code):
    enable(responder)
    res = ai(client)
    data = res.json()
    assert data["source"] == "procedural"
    assert (data["notice_code"], data["notice_params"]) == (code, {})
    assert "service IA" in data["notice"]
    assert FAKE_KEY not in res.text


def test_unexpected_exception_is_service_error(client, enable, monkeypatch):
    from app.services import gemini
    enable()
    monkeypatch.setattr(gemini.GeminiRenderer, "_call", lambda *a, **k: 1 / 0)
    data = ai(client).json()
    assert data["notice_code"] == "service_error"


# --- 422 : code + fields --------------------------------------------------------

@pytest.mark.parametrize("payload, fields", [
    ({"seed": "abc"}, ["seed"]),
    ({"seed": -1}, ["seed"]),
    ({"prompt": "x" * 301}, ["prompt"]),
    ({"size": "grand"}, ["size"]),
    ({"seed": "abc", "size": "grand"}, ["seed", "size"]),
])
def test_validation_422_has_code_and_fields(client, payload, fields):
    res = gen(client, **payload)
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "validation"
    assert body["fields"] == fields
    assert isinstance(body["detail"], list)  # format FastAPI conservé


def test_missing_field_and_missing_body(client):
    body = client.post("/api/generate", json={"engine": "gan"}).json()
    assert body["code"] == "validation" and body["fields"] == ["category"]
    body = client.post("/api/generate").json()
    assert body["code"] == "validation" and body["fields"] == []


@pytest.mark.parametrize("payload, field", [({"category": "poterie"}, "category"),
                                            ({"engine": "vae"}, "engine")])
def test_business_422_has_code_and_fields(client, payload, field):
    res = gen(client, **payload)
    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "validation" and body["fields"] == [field]
    assert isinstance(body["detail"], str) and field in body["detail"]


def test_assist_422_has_code_and_fields(client):
    res = client.post("/api/assist/enhance", json={"prompt": "ok", "category": "zellige", "lang": "de"})
    assert res.status_code == 422
    assert res.json()["code"] == "validation" and res.json()["fields"] == ["lang"]


# --- tableau de bord ---------------------------------------------------------------

def test_dashboard_totals_are_cumulative_beyond_history(client):
    cats = ["zellige", "tapis", "broderie"]
    for i in range(63):
        assert gen(client, category=cats[i % 3], seed=i, size=128).status_code == 200
    gen(client, category="poterie")  # échec : non compté
    data = client.get("/api/dashboard").json()
    assert data["total_motifs"] == 63
    assert data["repartition_par_categorie"] == {"zellige": 21, "tapis": 21, "broderie": 21}
    assert data["repartition_par_moteur"] == {"gan": 63, "diffusion": 0}
    assert data["repartition_par_source"] == {"procedural": 63, "gemini": 0, "trained_weights": 0}
    assert len(data["derniers_motifs"]) == 8
    assert len(main._HISTORY) == 8  # mémoire bornée
    assert data["derniers_motifs"][0]["seed"] == 62


def test_dashboard_items_have_seed_palette_source_thumb(client):
    gen(client, category="tapis", palette="berbere", seed=42)
    gen(client, palette="inconnue", seed=5)  # palette inconnue -> palette réelle utilisée
    items = client.get("/api/dashboard").json()["derniers_motifs"]
    assert items[1]["seed"] == 42 and items[1]["palette"] == "berbere"
    assert items[1]["source"] == "procedural"
    assert items[0]["palette"] == "zellige_classique"

    thumb = items[0]["thumb"]
    header, b64 = thumb.split(",", 1)
    assert header in ("data:image/webp;base64", "data:image/jpeg;base64")
    raw = base64.b64decode(b64)
    assert len(raw) < 20_000
    img = Image.open(io.BytesIO(raw))
    img.load()
    assert img.size == (160, 160)
    assert img.format in ("WEBP", "JPEG")


def test_dashboard_thumb_from_ai_render(client, enable):
    enable()
    ai(client)
    item = client.get("/api/dashboard").json()["derniers_motifs"][0]
    assert item["source"] == "gemini"
    img = Image.open(io.BytesIO(base64.b64decode(item["thumb"].split(",", 1)[1])))
    assert img.size == (160, 160)


# --- meta.assist ------------------------------------------------------------------------

def test_meta_assist_disabled(client):
    assert client.get("/api/meta").json()["assist"] == {
        "enabled": False, "model": None, "remaining_today": None}


def test_meta_assist_enabled_without_key_leak(client, enable_assist):  # noqa: F811
    enable_assist(daily_limit=42)
    res = client.get("/api/meta")
    assert res.json()["assist"] == {"enabled": True, "model": "deepseek-flash", "remaining_today": 42}
    assert res.json()["assist"] == client.get("/api/assist/status").json()
    assert DS_KEY not in res.text
