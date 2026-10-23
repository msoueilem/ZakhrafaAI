"""
Sélecteur de moteur de génération.

Comportement :
1. Si des poids GAN entraînés `gan_<category>_final.pth` sont trouvés dans
   `WEIGHTS_DIR` ET que torch est installé -> utilise le vrai GAN
   (app/models/gan.py), exactement comme décrit au §3.9 / §5.2 du rapport.
2. Sinon (cas par défaut de ce package, aucun poids fourni) -> utilise le
   générateur procédural (app/generators/), qui respecte les mêmes
   contraintes visuelles (catégorie, palette, résolution 256 en mode
   « gan » / 768 en mode « diffusion » par défaut, §3.8) sans dépendance
   lourde ni GPU.
3. Mode « diffusion » (libellé « Rendu IA ») : rendu hybride. Le générateur
   procédural dessine la géométrie (768 px), puis un modèle d'image Gemini
   la re-rend comme un objet artisanal réel (app/services/gemini.py). Sans
   clé, quota épuisé ou erreur du service IA, on renvoie l'image
   procédurale avec un `notice` explicatif — jamais d'erreur 500.
   Stable Diffusion (app/models/diffusion.py) n'est toujours pas branché.

Le GAN entraîné produit du 64x64 ; il est agrandi à la taille demandée
(256 par défaut). Les modèles chargés sont mis en cache par catégorie.

Cela garantit que l'application fonctionne "out of the box", tout en
restant compatible avec les vrais poids si l'utilisateur les fournit plus
tard (voir README.md, section "Brancher les vrais modèles").
"""
from __future__ import annotations

import base64
import functools
import io
import logging
import os
import random
import time
from pathlib import Path
from typing import Optional

from PIL import Image

from app.generators import broderie, tapis, zellige
from app.generators.utils import GenParams, resolve_size
from app.services import gemini

logger = logging.getLogger(__name__)

WEIGHTS_DIR = Path(os.environ.get("ZAKHRAFAAI_WEIGHTS_DIR", Path(__file__).resolve().parents[2] / "weights"))

GENERATORS = {
    "zellige": zellige,
    "tapis": tapis,
    "broderie": broderie,
}

VALID_CATEGORIES = list(GENERATORS.keys())
VALID_ENGINES = ["gan", "diffusion"]
VALID_PALETTES = ["fes_bleu", "zellige_classique", "terracotta", "emeraude", "berbere", "monochrome_ivoire"]

# résolution de l'image procédurale envoyée à Gemini comme base géométrique
AI_BASE_SIZE = 768


def _gan_weights_available(category: str) -> bool:
    path = WEIGHTS_DIR / f"gan_{category}_final.pth"
    return path.exists()


def image_to_data_url(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


class GenerationResult:
    def __init__(self, image: Image.Image, engine_used: str, source: str, elapsed_ms: float, seed: int,
                 model: Optional[str] = None, notice: Optional[str] = None):
        self.image = image
        self.engine_used = engine_used
        self.source = source  # "trained_weights" | "procedural" | "gemini"
        self.elapsed_ms = elapsed_ms
        self.seed = seed
        self.model = model  # modèle Gemini si source == "gemini"
        self.notice = notice  # raison du repli procédural en mode IA

    def to_dict(self):
        return {
            "image": image_to_data_url(self.image),
            "engine": self.engine_used,
            "source": self.source,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "seed": self.seed,
            "width": self.image.width,
            "height": self.image.height,
            "model": self.model,
            "notice": self.notice,
        }


def generate(
    category: str,
    engine: str = "gan",
    palette: str = "zellige_classique",
    seed: Optional[int] = None,
    size: Optional[int] = None,
    prompt: Optional[str] = None,
    client_ip: Optional[str] = None,
) -> GenerationResult:
    """`prompt` (souhait de style) n'est utilisé qu'en mode « diffusion »
    (rendu IA) ; `client_ip` sert à la limite de rendus IA par adresse."""
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category doit être l'une de {VALID_CATEGORIES}")
    if engine not in VALID_ENGINES:
        raise ValueError(f"engine doit être l'une de {VALID_ENGINES}")
    if palette not in VALID_PALETTES:
        palette = "zellige_classique"

    seed = seed if seed is not None else random.randint(0, 2**31 - 1)
    t0 = time.time()

    source = "procedural"
    model = notice = None
    if engine == "diffusion":
        image, source, model, notice = _generate_ai(category, palette, seed, size, prompt, client_ip)
    elif engine == "gan" and _gan_weights_available(category):
        try:
            image = _generate_with_torch_gan(category, seed, size)
            source = "trained_weights"
        except Exception:
            # Repli sur le générateur procédural si le chargement des poids
            # échoue (torch manquant, poids corrompus, etc.) — mais on le trace.
            logger.exception("Échec du GAN entraîné pour %r, repli sur le générateur procédural", category)
            params = GenParams(category=category, engine=engine, palette=palette, seed=seed, size=size)
            image = GENERATORS[category].generate(params)
    else:
        params = GenParams(category=category, engine=engine, palette=palette, seed=seed, size=size)
        image = GENERATORS[category].generate(params)

    elapsed_ms = (time.time() - t0) * 1000
    return GenerationResult(image=image, engine_used=engine, source=source, elapsed_ms=elapsed_ms, seed=seed,
                            model=model, notice=notice)


def _generate_ai(category: str, palette: str, seed: int, size: Optional[int],
                 prompt: Optional[str], client_ip: Optional[str]):
    """Procédural -> Gemini, avec repli procédural. Renvoie
    (image, source, model, notice)."""
    target = resolve_size("diffusion", size)
    procedural = GENERATORS[category].generate(
        GenParams(category=category, engine="diffusion", palette=palette, seed=seed, size=target))
    renderer = gemini.get_renderer()
    base = procedural
    if target != AI_BASE_SIZE and renderer.config.enabled:
        base = GENERATORS[category].generate(
            GenParams(category=category, engine="diffusion", palette=palette, seed=seed, size=AI_BASE_SIZE))

    outcome = renderer.render(
        base_image=base, category=category, palette=palette, seed=seed,
        size=target, prompt=prompt, client_ip=client_ip,
    )
    if outcome.ok:
        return outcome.image, "gemini", outcome.model, None
    return procedural, "procedural", None, outcome.notice


@functools.lru_cache(maxsize=len(VALID_CATEGORIES))
def _load_torch_gan(category: str):
    """Charge une seule fois les poids d'une catégorie (cache par processus)."""
    import torch

    from app.models.gan import Generator

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Generator(n_classes=len(VALID_CATEGORIES)).to(device)
    weights_path = WEIGHTS_DIR / f"gan_{category}_final.pth"
    model.load_state_dict(torch.load(weights_path, map_location=device, weights_only=True))
    model.eval()
    logger.info("Poids GAN chargés : %s (%s)", weights_path, device)
    return model, device


def _generate_with_torch_gan(category: str, seed: int, size: Optional[int]) -> Image.Image:
    """Exécute le vrai GAN entraîné (app/models/gan.py) si des poids sont
    présents dans WEIGHTS_DIR. Non exercé par défaut dans ce package car
    aucun poids n'est fourni (voir README). Le générateur sort du 64x64,
    agrandi à `size` (256 par défaut, borné à 128-1024)."""
    import torch

    model, device = _load_torch_gan(category)

    g = torch.Generator(device=device).manual_seed(seed)
    z = torch.randn(1, 100, 1, 1, device=device, generator=g)
    label = torch.tensor([VALID_CATEGORIES.index(category)], device=device)

    with torch.no_grad():
        out = model(z, label)[0]  # (C, H, W) in [-1, 1]

    out = ((out + 1) / 2 * 255).clamp(0, 255).byte().permute(1, 2, 0).cpu().numpy()
    img = Image.fromarray(out, "RGB")
    target = resolve_size("gan", size)
    return img.resize((target, target), Image.LANCZOS)
