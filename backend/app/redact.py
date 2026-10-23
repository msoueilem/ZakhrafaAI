"""
Masquage des secrets dans les textes venus d'un service amont (messages
d'erreur Google / DeepSeek) avant toute journalisation.

Un message d'erreur amont peut citer la clé API, un jeton ou un identifiant de
projet : il ne doit jamais être renvoyé au client, et n'est journalisé
qu'après passage par `redact()`.
"""
from __future__ import annotations

import re

MASK = "[masqué]"

_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),       # clé API Google
    re.compile(r"sk-[0-9A-Za-z]{16,}"),           # clé DeepSeek / style OpenAI
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),          # long jeton hexadécimal
    # long jeton base64 / base64url (au moins un chiffre ou symbole, pour ne
    # pas masquer un simple mot très long)
    re.compile(r"(?<![0-9A-Za-z+/_\-])(?=[0-9A-Za-z+/_\-]*[0-9+/_\-])"
               r"[0-9A-Za-z+/_\-]{32,}={0,2}"),
)


def redact(text: object) -> str:
    """Renvoie `text` (converti en chaîne) avec les secrets probables masqués."""
    out = str(text)
    for pattern in _PATTERNS:
        out = pattern.sub(MASK, out)
    return out
