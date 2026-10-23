"""Durcissement HTTP : 422 sans écho de la saisie, corps > 64 Ko refusés en
413 sur /api/*, HEAD accepté sur les pages."""
from __future__ import annotations

import asyncio
import json

from app import main

SECRET = "SECRET-SAISIE-0123456789"


# --- 422 : pas d'écho de la saisie ----------------------------------------------

def test_422_detail_has_no_input_nor_ctx(client):
    res = client.post("/api/generate", json={
        "category": "zellige", "engine": "diffusion", "prompt": SECRET * 20, "seed": -1})
    assert res.status_code == 422
    data = res.json()
    assert data["code"] == "validation" and set(data["fields"]) == {"prompt", "seed"}
    assert SECRET not in res.text
    for err in data["detail"]:
        assert set(err) <= {"loc", "msg", "type"} and {"loc", "msg", "type"} <= set(err)


def test_422_assist_has_no_input(client):
    res = client.post("/api/assist/plan", json={"idea": SECRET * 30, "lang": "xx"})
    assert res.status_code == 422
    assert SECRET not in res.text and "xx" not in json.dumps(res.json()["detail"])
    assert all("input" not in e and "ctx" not in e for e in res.json()["detail"])


# --- 413 : taille des corps ------------------------------------------------------

def _big_json(size: int) -> bytes:
    body = json.dumps({"category": "zellige", "prompt": "x" * size}).encode()
    return body


def test_content_length_over_64k_is_413(client):
    body = _big_json(main.MAX_BODY_BYTES)
    assert len(body) > main.MAX_BODY_BYTES
    res = client.post("/api/generate", content=body, headers={"content-type": "application/json"})
    assert res.status_code == 413 and res.json() == {"code": "payload_too_large"}


def test_streamed_body_over_64k_is_413(client):
    def chunks():
        for _ in range(10):
            yield b" " * 8192  # 80 Ko, sans Content-Length (chunked)
    res = client.post("/api/assist/enhance", content=chunks(),
                      headers={"content-type": "application/json"})
    assert res.status_code == 413 and res.json() == {"code": "payload_too_large"}


def test_body_under_limit_is_processed(client):
    res = client.post("/api/generate", content=json.dumps(
        {"category": "zellige", "engine": "gan", "seed": 1, "size": 128}).encode(),
        headers={"content-type": "application/json"})
    assert res.status_code == 200


def test_middleware_stops_reading_stream_at_limit():
    """Corps en plusieurs morceaux : lecture interrompue dès le dépassement."""
    sent, reads = [], []
    chunk = b"a" * 16384

    async def app(scope, receive, send):
        while True:
            msg = await receive()
            if not msg.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive():
        reads.append(1)
        return {"type": "http.request", "body": chunk, "more_body": len(reads) < 20}

    async def send(msg):
        sent.append(msg)

    mw = main.BodySizeLimitMiddleware(app)
    scope = {"type": "http", "method": "POST", "path": "/api/generate", "headers": []}
    asyncio.run(mw(scope, receive, send))
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"]) == {"code": "payload_too_large"}
    assert len(reads) == 5  # 5 x 16 Ko > 64 Ko : arrêt immédiat


def test_middleware_ignores_non_api_paths():
    called = []

    async def app(scope, receive, send):
        called.append(scope["path"])

    mw = main.BodySizeLimitMiddleware(app)
    scope = {"type": "http", "method": "POST", "path": "/studio",
             "headers": [(b"content-length", b"999999")]}
    asyncio.run(mw(scope, None, None))
    assert called == ["/studio"]
