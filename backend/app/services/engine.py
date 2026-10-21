"""
Sélecteur de moteur de génération.

Comportement :
1. Si des poids GAN entraînés `gan_<category>_final.pth` sont trouvés dans
   `WEIGHTS_DIR` ET que torch est installé -> utilise le vrai GAN
   (app/models/gan.py), exactement comme décrit au §3.9 / §5.2 du rapport.
2. Sinon (cas par défaut de ce package, aucun poids fourni) -> utilise le
   générateur procédural (app/generators/), qui respecte les mêmes
   contraintes visuelles (catégorie, palette, résolution GAN=256 /
   Diffusion=768 par défaut, §3.8) sans dépendance lourde ni GPU.

Cela garantit que l'application fonctionne "out of the box", tout en
restant compatible avec les vrais poids si l'utilisateur les fournit plus
tard (voir README.md, section "Brancher les vrais modèles").
"""
from __future__ import annotations

import base64
import io
import os
import random
import time
from pathlib import Path
from typing import Optional

from PIL import Image

from app.generators import broderie, tapis, zellige
from app.generators.utils import GenParams

WEIGHTS_DIR = Path(os.environ.get("ZAKHRAFAAI_WEIGHTS_DIR", Path(__file__).resolve().parents[2] / "weights"))

GENERATORS = {
    "zellige": zellige,
    "tapis": tapis,
    "broderie": broderie,
}

VALID_CATEGORIES = list(GENERATORS.keys())
VALID_ENGINES = ["gan", "diffusion"]
VALID_PALETTES = ["fes_bleu", "zellige_classique", "terracotta", "emeraude", "berbere", "monochrome_ivoire"]


def _gan_weights_available(category: str) -> bool:
    path = WEIGHTS_DIR / f"gan_{category}_final.pth"
    return path.exists()


def image_to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


class GenerationResult:
    def __init__(self, image: Image.Image, engine_used: str, source: str, elapsed_ms: float, seed: int):
        self.image = image
        self.engine_used = engine_used
        self.source = source  # "trained_weights" | "procedural"
        self.elapsed_ms = elapsed_ms
        self.seed = seed

    def to_dict(self):
        return {
            "image": image_to_data_url(self.image),
            "engine": self.engine_used,
            "source": self.source,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "seed": self.seed,
            "width": self.image.width,
            "height": self.image.height,
        }


def generate(
    category: str,
    engine: str = "gan",
    palette: str = "zellige_classique",
    seed: Optional[int] = None,
    size: Optional[int] = None,
) -> GenerationResult:
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category doit être l'une de {VALID_CATEGORIES}")
    if engine not in VALID_ENGINES:
        raise ValueError(f"engine doit être l'une de {VALID_ENGINES}")
    if palette not in VALID_PALETTES:
        palette = "zellige_classique"

    seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    t0 = time.time()

    source = "procedural"
    if engine == "gan" and _gan_weights_available(category):
        try:
            image = _generate_with_torch_gan(category, seed, size)
            source = "trained_weights"
        except Exception:
            # Repli silencieux sur le générateur procédural si le
            # chargement des poids échoue (torch manquant, poids corrompus, etc.)
            params = GenParams(category=category, engine=engine, palette=palette, seed=seed, size=size)
            image = GENERATORS[category].generate(params)
    else:
        params = GenParams(category=category, engine=engine, palette=palette, seed=seed, size=size)
        image = GENERATORS[category].generate(params)

    elapsed_ms = (time.time() - t0) * 1000
    return GenerationResult(image=image, engine_used=engine, source=source, elapsed_ms=elapsed_ms, seed=seed)


def _generate_with_torch_gan(category: str, seed: int, size: Optional[int]) -> Image.Image:
    """Charge et exécute le vrai GAN entraîné (app/models/gan.py) si des
    poids sont présents dans WEIGHTS_DIR. Non exercé par défaut dans ce
    package car aucun poids n'est fourni (voir README)."""
    import torch

    from app.models.gan import Generator

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Generator(n_classes=len(VALID_CATEGORIES)).to(device)
    weights_path = WEIGHTS_DIR / f"gan_{category}_final.pth"
    model.load_state_dict(torch.load(weights_path, map_location=device))
    model.eval()

    g = torch.Generator(device=device).manual_seed(seed)
    z = torch.randn(1, 100, 1, 1, device=device, generator=g)
    label = torch.tensor([VALID_CATEGORIES.index(category)], device=device)

    with torch.no_grad():
        out = model(z, label)[0]  # (C, H, W) in [-1, 1]

    out = ((out + 1) / 2 * 255).clamp(0, 255).byte().permute(1, 2, 0).cpu().numpy()
    img = Image.fromarray(out, "RGB")
    if size:
        img = img.resize((size, size), Image.LANCZOS)
    return img
