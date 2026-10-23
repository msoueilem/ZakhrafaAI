"""
Utilitaires partagés pour les générateurs de motifs ZakhrafaAI.

Ces générateurs implémentent, de façon procédurale, la même sortie que
décrivent les modules GAN / Diffusion du rapport (backend/models/gan.py,
diffusion pipeline) : une image RGB conditionnée par une catégorie
(zellige / tapis / broderie) et un style de couleur.

Pourquoi procédural et pas un vrai GAN/Diffusion chargé depuis des poids ?
Le rapport documente que les poids entraînés (`gan_<pattern>_final.pth`)
et Stable Diffusion nécessitent : un GPU, plusieurs Go de poids, et pour
la diffusion un accès à Hugging Face. Rien de tout cela n'est disponible
dans cet environnement de packaging. Pour livrer une application qui
*fonctionne réellement de bout en bout sans erreur*, ce module fournit un
moteur de synthèse géométrique déterministe-mais-varié (seed = bruit z)
qui respecte les codes visuels marocains (symétrie, répétition, entrelacs)
décrits en section 1.1 et 4 du rapport.

`backend/app/models/gan.py` et `backend/app/models/diffusion.py` contiennent
l'architecture réelle (PyTorch) décrite dans le rapport, prête à être
branchée : il suffit de fournir des poids entraînés et d'installer torch.
"""
from __future__ import annotations

import colorsys
import math
import random
from dataclasses import dataclass
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

Color = Tuple[int, int, int]

# ---------------------------------------------------------------------------
# Palettes culturelles (cf. rapport §1.1 : zellige = mosaïques colorées,
# tapis = motifs berbères, broderie = ornements floraux)
# ---------------------------------------------------------------------------

PALETTES = {
    "fes_bleu": ["#0B3D5C", "#1B6FA8", "#F2E9D8", "#C9A227", "#0F2A3D"],
    "zellige_classique": ["#0B4F6C", "#01BAEF", "#FFFFFF", "#F2C641", "#7A1E2B"],
    "terracotta": ["#B5533C", "#E0A96D", "#3E2723", "#F2E9D8", "#2E7D5B"],
    "emeraude": ["#04471C", "#2E7D5B", "#F2E9D8", "#C9A227", "#0F2A3D"],
    "berbere": ["#7A1E2B", "#C9A227", "#3E2723", "#E0A96D", "#0F2A3D"],
    "monochrome_ivoire": ["#2B2B2B", "#5C5C5C", "#F2E9D8", "#8C8C8C", "#111111"],
}

DEFAULT_PALETTE = "zellige_classique"


def hex_to_rgb(h: str) -> Color:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def get_palette(name: str) -> List[Color]:
    hexes = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    return [hex_to_rgb(h) for h in hexes]


def jitter_color(c: Color, amount: int, rng: random.Random) -> Color:
    return tuple(
        max(0, min(255, ch + rng.randint(-amount, amount))) for ch in c
    )  # type: ignore


@dataclass
class GenParams:
    category: str  # zellige | tapis | broderie
    engine: str  # gan | diffusion
    palette: str = DEFAULT_PALETTE
    seed: int | None = None
    size: int | None = None  # taille finale carrée ; None = défaut selon engine
    color_mode: str = "palette"  # palette | monochrome | random
    cells: int | None = None  # force la densité de la grille (base du rendu IA : motifs plus grands)


def resolve_size(engine: str, requested: int | None) -> int:
    """Reproduit les résolutions réellement utilisées dans le rapport (§3.8):
    GAN ~ 256x256 (entraînement compact), Diffusion par défaut 768x768."""
    if requested:
        return max(128, min(1024, requested))
    return 256 if engine == "gan" else 768


def new_canvas(size: int, bg: Color) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    return img, draw


def add_texture_noise(img: Image.Image, rng: random.Random, strength: float = 6.0) -> Image.Image:
    """Léger grain pour éviter un rendu trop 'vectoriel plat', comme le
    bruit gaussien décrit dans le processus forward de diffusion (§4.2)."""
    import numpy as np

    arr = np.asarray(img).astype("int16")
    noise = (np.random.default_rng(rng.randint(0, 2**31 - 1)).normal(0, strength, arr.shape)).astype("int16")
    arr = np.clip(arr + noise, 0, 255).astype("uint8")
    return Image.fromarray(arr, "RGB")


def finish(img: Image.Image, engine: str) -> Image.Image:
    """Post-traitement (§3.7 du rapport) : léger ajustement contraste /
    luminosité, plus net pour la diffusion (haute qualité) que pour le GAN
    (rapide), conformément aux conclusions du §8 du rapport."""
    if engine == "diffusion":
        img = img.filter(ImageFilter.SMOOTH_MORE)
        img = ImageEnhance.Contrast(img).enhance(1.08)
        img = ImageEnhance.Color(img).enhance(1.05)
        img = img.filter(ImageFilter.SHARPEN)
    else:
        img = ImageEnhance.Contrast(img).enhance(1.03)
    return img


def star_polygon(cx: float, cy: float, r_outer: float, r_inner: float, points: int, rotation: float = 0.0):
    coords = []
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        angle = math.pi * i / points + rotation
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return coords


def regular_polygon(cx: float, cy: float, r: float, sides: int, rotation: float = 0.0):
    return [
        (
            cx + r * math.cos(2 * math.pi * i / sides + rotation),
            cy + r * math.sin(2 * math.pi * i / sides + rotation),
        )
        for i in range(sides)
    ]
