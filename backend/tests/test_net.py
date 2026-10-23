"""Adresse client (X-Real-IP validé), clés IPv6 /64 et dictionnaire des
limites par IP borné — partagés par /api/generate et /api/assist/*."""
from __future__ import annotations

import json
from collections import OrderedDict

import httpx
import pytest
from starlette.requests import Request

from app import net
from app.services import deepseek


def make_request(real_ip=None, host="192.0.2.10"):
    headers = [(b"x-real-ip", real_ip.encode())] if real_ip is not None else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers,
                    "client": (host, 1234) if host else None})


@pytest.mark.parametrize("header, expected", [
    ("203.0.113.7", "203.0.113.7"),
    ("  203.0.113.7 ", "203.0.113.7"),
    ("2001:DB8:0:0::1", "2001:db8::1"),          # forme normalisée
    ("pas-une-ip", "192.0.2.10"),                 # invalide => socket
    ("203.0.113.7, 10.0.0.1", "192.0.2.10"),
    ("", "192.0.2.10"),
    (None, "192.0.2.10"),
])
def test_client_ip_reads_valid_x_real_ip_else_socket(header, expected):
    assert net.client_ip(make_request(header)) == expected


def test_client_ip_without_socket():
    assert net.client_ip(make_request(None, host=None)) is None


def test_main_and_assist_share_client_ip():
    from app import main
    from app.routers import assist
    assert main.client_ip is net.client_ip and assist.client_ip is net.client_ip


@pytest.mark.parametrize("ip, key", [
    ("203.0.113.7", "203.0.113.7"),
    ("2001:db8:1:2:aaaa::1", "2001:db8:1:2::/64"),
    ("2001:db8:1:2:ffff:ffff:ffff:ffff", "2001:db8:1:2::/64"),
    ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
    ("::ffff:203.0.113.7", "203.0.113.7"),
    ("testclient", "testclient"),
    (None, "inconnue"),
])
def test_ip_key_groups_ipv6_by_64(ip, key):
    assert net.ip_key(ip) == key


def test_ip_hits_is_bounded_and_evicts_least_recent():
    store: OrderedDict = OrderedDict()
    for i in range(5):
        net.ip_hits(store, f"k{i}", max_keys=3).append(float(i))
        assert len(store) <= 3
    assert list(store) == ["k2", "k3", "k4"]
    net.ip_hits(store, "k2", max_keys=3)   # k2 redevient la plus récente
    net.ip_hits(store, "k5", max_keys=3)   # évince k3
    assert list(store) == ["k4", "k2", "k5"]
    assert list(store["k2"]) == [2.0]       # fenêtre conservée


def test_default_cap_is_4096():
    assert net.IP_KEYS_MAX == 4096
    store: OrderedDict = OrderedDict()
    for i in range(4096 + 50):
        net.ip_hits(store, str(i))
    assert len(store) == 4096 and "0" not in store and str(4096 + 49) in store


# --- intégration : les deux services ----------------------------------------

def _ok(request):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"prompt": "ok"})},
                                                  "finish_reason": "stop"}]})


@pytest.fixture()
def assistant(tmp_path):
    def _make(**overrides):
        cfg = dict(api_key="sk-test", daily_limit=1000, per_ip_limit=1, timeout=5,
                   data_dir=tmp_path / "data")
        cfg.update(overrides)
        return deepseek.reset_assistant(deepseek.DeepSeekConfig(**cfg),
                                        transport=httpx.MockTransport(_ok))
    return _make


def enhance(client, ip):
    return client.post("/api/assist/enhance", json={"prompt": "bleu", "category": "zellige"},
                       headers={"X-Real-IP": ip})


def test_assist_ipv6_same_64_shares_limit(client, assistant):
    assistant()
    assert enhance(client, "2001:db8:5:6::1").status_code == 200
    assert enhance(client, "2001:db8:5:6:ffff::9").status_code == 429  # même /64
    assert enhance(client, "2001:db8:5:7::1").status_code == 200       # autre /64


def test_assist_invalid_x_real_ip_falls_back_to_socket(client, assistant):
    assistant()
    assert enhance(client, "n'importe-quoi").status_code == 200
    # autre valeur invalide => même adresse de socket => limite atteinte
    assert enhance(client, "autre-chose").status_code == 429


def test_assist_ip_store_is_capped(client, assistant, monkeypatch):
    monkeypatch.setattr(net, "IP_KEYS_MAX", 8)
    svc = assistant(per_ip_limit=5)
    for i in range(20):
        assert enhance(client, f"198.51.100.{i}").status_code == 200
    assert len(svc._ip_hits) == 8


def test_gemini_ipv6_same_64_shares_limit_and_store_is_capped(monkeypatch, tmp_path):
    from PIL import Image
    from app.services import gemini
    monkeypatch.setattr(net, "IP_KEYS_MAX", 4)
    renderer = gemini.reset_renderer(gemini.GeminiConfig(
        api_key="k", per_ip_limit=1, daily_limit=1000, data_dir=tmp_path / "data"),
        transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    base = Image.new("RGB", (8, 8))

    def render(ip, seed):
        return renderer.render(base_image=base, category="zellige", palette="fes_bleu",
                               seed=seed, size=8, prompt=None, client_ip=ip)

    assert render("2001:db8:9:9::1", 1).notice_code == "service_error"
    assert render("2001:db8:9:9::2", 2).notice_code == "ip_limit"
    for i in range(10):
        render(f"198.51.100.{i}", 10 + i)
    assert len(renderer._ip_hits) == 4
