"""Configuration de déploiement : pairs de confiance de --forwarded-allow-ips
(Dockerfile), interprétés avec l'analyseur d'uvicorn lui-même."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

DOCKERFILE = Path(__file__).resolve().parents[2] / "Dockerfile"


def _cmd() -> list:
    if not DOCKERFILE.exists():
        pytest.skip("Dockerfile absent (image de production)")
    text = DOCKERFILE.read_text(encoding="utf-8").replace("\\\n", " ")
    match = re.search(r"^CMD\s+(\[.*\])\s*$", text, re.M)
    assert match, "CMD au format exec attendu"
    return json.loads(match.group(1))


def test_forwarded_allow_ips_restricted_to_private_ranges():
    from uvicorn.middleware.proxy_headers import _TrustedHosts

    cmd = _cmd()
    assert "--proxy-headers" in cmd
    value = cmd[cmd.index("--forwarded-allow-ips") + 1]
    assert value == "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"
    trusted = _TrustedHosts(value)
    assert not trusted.always_trust
    # passerelles du pont Docker (nginx sur l'hôte), loopback du HEALTHCHECK
    for ip in ("127.0.0.1", "172.17.0.1", "172.18.0.1", "10.0.0.1", "192.168.1.1"):
        assert ip in trusted
    for ip in ("8.8.8.8", "203.0.113.5", "172.32.0.1", "2001:db8::1"):
        assert ip not in trusted
