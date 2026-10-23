"""Utilitaires de test."""
from __future__ import annotations

import base64
import io

from PIL import Image


def decode_png(data_url: str) -> Image.Image:
    """Décode le data URL PNG renvoyé par /api/generate."""
    prefix = "data:image/png;base64,"
    assert data_url.startswith(prefix)
    img = Image.open(io.BytesIO(base64.b64decode(data_url[len(prefix):])))
    assert img.format == "PNG"
    img.load()
    return img
