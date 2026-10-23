"""
Adresse du client et clés des limites par IP (partagé par /api/generate et
/api/assist/*).

- `client_ip()` : le conteneur n'est joignable que via nginx, qui écrase
  X-Real-IP avec $remote_addr ; à défaut (lancement direct, en-tête absent ou
  invalide), l'adresse de la socket.
- `ip_key()` : clé de limitation ; une adresse IPv6 est regroupée par son /64
  (un abonné reçoit en général tout un /64 et pourrait sinon changer
  d'adresse à chaque requête).
- `ip_hits()` : fenêtre de tentatives d'une clé, dans un dictionnaire borné à
  IP_KEYS_MAX entrées (la moins récemment vue est évincée) — coût O(1) par
  requête, sans balayage global.
"""
from __future__ import annotations

import ipaddress
from collections import OrderedDict, deque
from typing import Deque, Optional

from fastapi import Request

IP_KEYS_MAX = 4096
UNKNOWN = "inconnue"
IPV6_PREFIX = 64


def _parse_ip(value: Optional[str]):
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_ip(request: Request) -> Optional[str]:
    """X-Real-IP s'il contient une adresse IP valide, sinon l'adresse de la socket."""
    real_ip = _parse_ip(request.headers.get("x-real-ip"))
    if real_ip is not None:
        return str(real_ip)
    return request.client.host if request.client else None


def ip_key(ip: Optional[str]) -> str:
    """IPv4 telle quelle, IPv6 réduite à son /64 (IPv4 mappée => IPv4)."""
    addr = _parse_ip(ip)
    if addr is None:
        return (ip or UNKNOWN)[:64]
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.IPv6Network((addr, IPV6_PREFIX), strict=False))
    return str(addr)


def ip_hits(store: "OrderedDict[str, Deque[float]]", key: str,
            max_keys: Optional[int] = None) -> Deque[float]:
    """Fenêtre de `key` (créée si besoin). À appeler sous le verrou du service.
    L'entrée devient la plus récente ; au-delà de `max_keys` clés, la plus
    ancienne est évincée."""
    hits = store.get(key)
    if hits is not None:
        store.move_to_end(key)
        return hits
    limit = IP_KEYS_MAX if max_keys is None else max_keys
    while len(store) >= max(1, limit):
        store.popitem(last=False)
    hits = store[key] = deque()
    return hits
