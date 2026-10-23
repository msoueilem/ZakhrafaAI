"""Tests du rendu IA (Gemini) — l'API Google est entièrement simulée
(httpx.MockTransport), aucun appel réseau."""
from __future__ import annotations

import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.services import gemini

from .helpers import decode_png

FAKE_KEY = "cle-de-test-XYZ"


def png_b64(size=1024, color=(180, 40, 30)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def image_response(**_):
    return httpx.Response(200, json={"candidates": [{
        "content": {"parts": [
            {"text": "pensée", "thought": True},
            {"text": "Voici le rendu."},
            {"inlineData": {"mimeType": "image/png", "data": png_b64()}},
        ]},
        "finishReason": "STOP",
    }]})


class FakeGemini:
    """Transport simulé qui enregistre les requêtes reçues."""

    def __init__(self, responder=image_response):
        self.responder = responder
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responder(request=request)

    @property
    def calls(self) -> int:
        return len(self.requests)


@pytest.fixture()
def enable(tmp_path):
    def _enable(responder=image_response, **overrides):
        fake = FakeGemini(responder)
        cfg = dict(api_key=FAKE_KEY, model="gemini-3.1-flash-lite-image",
                   daily_limit=60, per_ip_limit=5, timeout=5, data_dir=tmp_path / "data")
        cfg.update(overrides)
        gemini.reset_renderer(gemini.GeminiConfig(**cfg), transport=httpx.MockTransport(fake))
        return fake
    return _enable


def ai(client, ip="203.0.113.7", **payload):
    body = {"category": "zellige", "engine": "diffusion", "palette": "fes_bleu", "seed": 7, **payload}
    return client.post("/api/generate", json=body, headers={"X-Real-IP": ip})


# --- désactivé ----------------------------------------------------------------

def test_disabled_without_key_falls_back_with_notice(client):
    data = ai(client).json()
    assert data["source"] == "procedural"
    assert data["model"] is None
    assert "clé" in data["notice"]
    assert decode_png(data["image"]).size == (768, 768)


def test_fast_mode_has_no_notice_and_ignores_prompt(client, enable):
    fake = enable()
    data = ai(client, engine="gan", prompt="couleurs pastel").json()
    assert data["source"] == "procedural"
    assert data["notice"] is None
    assert fake.calls == 0


# --- succès -------------------------------------------------------------------

def test_success_returns_gemini_png(client, enable):
    fake = enable()
    res = ai(client, prompt="  tons plus chauds  ")
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "gemini"
    assert data["model"] == "gemini-3.1-flash-lite-image"
    assert data["notice"] is None
    img = decode_png(data["image"])
    assert img.size == (768, 768)  # redimensionné à la taille demandée
    assert img.getpixel((10, 10)) == (180, 40, 30)

    dash = client.get("/api/dashboard").json()
    assert dash["repartition_par_moteur"]["diffusion"] == 1
    assert dash["repartition_par_source"]["gemini"] == 1
    assert dash["derniers_motifs"][0]["source"] == "gemini"

    assert fake.calls == 1
    req = fake.requests[0]
    assert req.url.path.endswith("/models/gemini-3.1-flash-lite-image:generateContent")
    assert req.headers["x-goog-api-key"] == FAKE_KEY
    assert FAKE_KEY not in str(req.url)
    body = json.loads(req.content)
    text, inline = body["contents"][0]["parts"]
    assert "zellige" in text["text"]
    assert "Souhait de style de l'utilisateur" in text["text"] and "« tons plus chauds »" in text["text"]
    assert "same layout, geometry" in text["text"]
    base = Image.open(io.BytesIO(base64.b64decode(inline["inline_data"]["data"])))
    assert base.format == "PNG" and base.size == (768, 768)
    assert body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
    assert body["generationConfig"]["imageConfig"] == {"aspectRatio": "1:1"}


def test_base_image_is_768_even_for_other_sizes(client, enable):
    fake = enable()
    data = ai(client, size=512).json()
    assert data["source"] == "gemini" and (data["width"], data["height"]) == (512, 512)
    base_b64 = json.loads(fake.requests[0].content)["contents"][0]["parts"][1]["inline_data"]["data"]
    assert Image.open(io.BytesIO(base64.b64decode(base_b64))).size == (768, 768)


def test_zellige_base_uses_larger_motifs(client, enable):
    from app.generators import zellige
    from app.generators.utils import GenParams

    fake = enable()
    ai(client)
    base_b64 = json.loads(fake.requests[0].content)["contents"][0]["parts"][1]["inline_data"]["data"]
    sent = Image.open(io.BytesIO(base64.b64decode(base_b64))).convert("RGB")
    loose = zellige.generate(GenParams(category="zellige", engine="diffusion", palette="fes_bleu",
                                       seed=7, size=768, cells=3))
    dense = zellige.generate(GenParams(category="zellige", engine="diffusion", palette="fes_bleu",
                                       seed=7, size=768))
    assert sent.tobytes() == loose.tobytes()
    assert sent.tobytes() != dense.tobytes()


@pytest.mark.parametrize("category, word", [("tapis", "rug"), ("broderie", "embroidery")])
def test_prompt_depends_on_category(client, enable, category, word):
    fake = enable()
    assert ai(client, category=category).json()["source"] == "gemini"
    assert word in json.loads(fake.requests[0].content)["contents"][0]["parts"][0]["text"]


# --- échecs => repli ----------------------------------------------------------

def _no_image(**_):
    return httpx.Response(200, json={"candidates": [{
        "content": {"parts": [{"text": "Je ne peux pas générer cette image."}]},
        "finishReason": "IMAGE_SAFETY"}]})


def _blocked(**_):
    return httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}})


def _http_500(**_):
    return httpx.Response(500, json={"error": {"code": 500, "message": "Internal error", "status": "INTERNAL"}})


def _timeout(request, **_):
    raise httpx.ReadTimeout("trop long", request=request)


def _garbage(**_):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": "pas-du-base64-valide!!"}}]}}]})


@pytest.mark.parametrize("responder, fragment", [
    (_no_image, "aucune image"),
    (_blocked, "bloquée"),
    (_http_500, "HTTP 500"),
    (_timeout, "délai dépassé"),
    (_garbage, "illisible"),
])
def test_failures_fall_back_without_counting_quota(client, enable, caplog, responder, fragment):
    enable(responder)
    with caplog.at_level("WARNING"):
        res = ai(client)
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "procedural"
    assert data["model"] is None
    # notice : phrase fixe par code ; le détail de l'échec ne va qu'aux journaux
    assert data["notice"] == gemini.notice_for(data["notice_code"])
    assert "service IA" in data["notice"] and fragment in caplog.text
    assert FAKE_KEY not in res.text
    assert decode_png(data["image"]).size == (768, 768)
    assert client.get("/api/meta").json()["ai"]["remaining_today"] == 60


def test_key_never_logged_on_error(client, enable, caplog):
    enable(_http_500)
    with caplog.at_level("DEBUG"):
        ai(client)
    assert FAKE_KEY not in caplog.text
    assert "HTTP 500" in caplog.text


# --- quotas -------------------------------------------------------------------

def test_daily_limit_reached_falls_back(client, enable):
    fake = enable(daily_limit=2, per_ip_limit=100)
    assert [ai(client, seed=s).json()["source"] for s in (1, 2)] == ["gemini", "gemini"]
    data = ai(client, seed=3).json()
    assert data["source"] == "procedural"
    assert "Quota journalier" in data["notice"]
    assert fake.calls == 2
    assert client.get("/api/meta").json()["ai"]["remaining_today"] == 0


def test_per_ip_limit_uses_x_real_ip_and_counts_attempts(client, enable):
    fake = enable(_http_500, per_ip_limit=2)
    for s in (1, 2):  # tentatives échouées : comptent pour l'IP
        assert "service IA" in ai(client, seed=s, ip="198.51.100.1").json()["notice"]
    data = ai(client, seed=3, ip="198.51.100.1").json()
    assert data["source"] == "procedural" and "votre adresse" in data["notice"]
    assert fake.calls == 2
    # une autre IP n'est pas affectée
    assert "service IA" in ai(client, seed=4, ip="198.51.100.2").json()["notice"]
    assert fake.calls == 3


def test_cache_hit_does_not_call_or_count(client, enable):
    fake = enable(per_ip_limit=1)
    first = ai(client, prompt="vert profond").json()
    second = ai(client, prompt="vert profond").json()  # même IP, limite 1 : servi par le cache
    assert first["source"] == second["source"] == "gemini"
    assert first["image"] == second["image"]
    assert fake.calls == 1
    assert client.get("/api/meta").json()["ai"]["remaining_today"] == 59
    # un autre souhait = une autre clé de cache => nouvel appel (bloqué ici par l'IP)
    assert "votre adresse" in ai(client, prompt="bleu nuit").json()["notice"]


def test_counter_persists_across_reload(client, enable, tmp_path):
    enable(daily_limit=5)
    ai(client, seed=1)
    ai(client, seed=2)
    state = json.loads((tmp_path / "data" / gemini.USAGE_FILENAME).read_text())
    assert state["count"] == 2
    # « redémarrage » : nouvelle instance relisant le fichier d'état
    enable(daily_limit=5)
    assert client.get("/api/meta").json()["ai"]["remaining_today"] == 3


def test_counter_from_previous_day_is_reset(client, enable, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / gemini.USAGE_FILENAME).write_text(json.dumps({"day": "2000-01-01", "count": 59}))
    enable()
    assert client.get("/api/meta").json()["ai"]["remaining_today"] == 60


# --- validation / méta ----------------------------------------------------------

def test_prompt_too_long_is_422(client):
    assert ai(client, prompt="x" * 301).status_code == 422
    assert ai(client, prompt="x" * 300).status_code == 200
    # les espaces autour sont retirés avant le contrôle de longueur
    assert ai(client, prompt="  " + "x" * 300 + "  ").status_code == 200


def test_meta_ai_disabled(client):
    assert client.get("/api/meta").json()["ai"] == {"enabled": False, "model": None, "remaining_today": None}


def test_meta_ai_enabled_without_key(client, enable):
    enable()
    res = client.get("/api/meta")
    assert res.json()["ai"] == {"enabled": True, "model": "gemini-3.1-flash-lite-image", "remaining_today": 60}
    assert FAKE_KEY not in res.text


def test_config_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")
    monkeypatch.setenv("GEMINI_DAILY_LIMIT", "10")
    monkeypatch.setenv("GEMINI_PER_IP_LIMIT", "abc")  # invalide => défaut
    cfg = gemini.GeminiConfig.from_env()
    assert cfg.enabled and cfg.model == "gemini-3-pro-image"
    assert (cfg.daily_limit, cfg.per_ip_limit, cfg.timeout) == (10, 5, 90.0)
    assert FAKE_KEY not in repr(cfg)


# --- fuite du texte d'erreur amont ------------------------------------------

LEAKED_KEY = "AIzaSyD-FAKEfake0123456789abcdefGHIJKL"


def _http_400_quoting_key(**_):
    return httpx.Response(400, json={"error": {
        "code": 400, "status": "INVALID_ARGUMENT",
        "message": f"API key not valid: {LEAKED_KEY} (projects/123456789012)"}})


def test_upstream_error_text_never_reaches_client_and_is_redacted_in_logs(client, enable, caplog):
    enable(_http_400_quoting_key)
    with caplog.at_level("DEBUG"):
        res = ai(client)
    data = res.json()
    assert (data["source"], data["notice_code"]) == ("procedural", "service_error")
    assert data["notice"] == gemini.NOTICES["service_error"]
    assert LEAKED_KEY not in res.text and "API key not valid" not in res.text
    assert "123456789012" not in res.text
    # journalisé pour le diagnostic, mais clé masquée
    assert "HTTP 400" in caplog.text and "API key not valid" in caplog.text
    assert LEAKED_KEY not in caplog.text and "AIza" not in caplog.text
    assert "[masqué]" in caplog.text


def test_notice_is_fixed_per_code():
    for code in ("ai_disabled", "timeout", "blocked", "service_error"):
        assert gemini.notice_for(code) == gemini.NOTICES[code]
    assert "30/jour" in gemini.notice_for("daily_limit", {"n": 30})
    assert "5 par 10 min" in gemini.notice_for("ip_limit", {"n": 5})
    assert gemini.notice_for("inconnu") == gemini.NOTICES["service_error"]


def test_redact_masks_tokens():
    from app.redact import MASK, redact
    hex_token = "0123456789abcdef" * 3
    b64_token = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo0MTIzNDU2Nzg5MA=="
    text = (f"cle {LEAKED_KEY} ds sk-ABCDEFabcdef0123456789 hex {hex_token} "
            f"b64 {b64_token} fin")
    out = redact(text)
    for secret in (LEAKED_KEY, "sk-ABCDEFabcdef0123456789", hex_token, b64_token):
        assert secret not in out
    assert out.count(MASK) == 4
    assert out.startswith("cle ") and out.endswith(" fin")
    # texte ordinaire intact (y compris un mot long sans chiffre)
    plain = "Requête refusée : anticonstitutionnellementxxxxxxxxxx, quota dépassé (HTTP 429)."
    assert redact(plain) == plain
