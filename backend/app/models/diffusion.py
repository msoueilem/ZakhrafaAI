"""
Point d'intégration Stable Diffusion, tel que décrit au §4.1 (modèle de
diffusion conditionnel, U-Net + cross-attention, scheduler accéléré) et
§5.4 (résolution par défaut 768x768, guidance scale ajustée) du rapport.

Comme pour app/models/gan.py, ce module nécessite `diffusers` + `torch`
+ un accès réseau pour télécharger les poids Stable Diffusion (ou un
checkpoint local + LoRA fine-tuné sur le dataset zellige/tapis/broderie,
cf. §7 "Resultat de diffusion (stable diffusion +LoRA)"). Aucun de ces
prérequis n'est disponible dans l'environnement de packaging, donc l'API
utilise par défaut le générateur procédural (app/generators/).

Pour brancher un vrai pipeline Stable Diffusion + LoRA une fois déployé
sur une machine avec GPU :

    from app.models.diffusion import build_pipeline
    pipe = build_pipeline(lora_path="loras/zellige_fes.safetensors")
    image = pipe(prompt="zellige bleu, style Fès, motif géométrique",
                 num_inference_steps=30, guidance_scale=7.5,
                 height=768, width=768).images[0]
"""
from __future__ import annotations

from typing import Optional

try:
    import torch
    from diffusers import StableDiffusionPipeline

    DIFFUSERS_AVAILABLE = True
except ImportError:  # pragma: no cover
    DIFFUSERS_AVAILABLE = False


CATEGORY_PROMPTS = {
    "zellige": "moroccan zellige mosaic, intricate geometric star tiling, {style}, symmetrical, top-down, crisp tile grout lines",
    "tapis": "moroccan berber rug pattern, tribal diamond motifs, {style}, woven texture, flat lay",
    "broderie": "moroccan embroidery ornament, floral and geometric threadwork, {style}, fine stitching detail",
}

NEGATIVE_PROMPT = "blurry, watermark, text, photo of a person, low quality, distorted"


def build_prompt(category: str, style: str = "authentic traditional colors") -> str:
    template = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS["zellige"])
    return template.format(style=style)


def build_pipeline(
    base_model: str = "runwayml/stable-diffusion-v1-5",
    lora_path: Optional[str] = None,
    device: str = "cuda",
):
    """Construit un pipeline Stable Diffusion (+ LoRA optionnel) tel que
    mentionné §7 du rapport. Nécessite diffusers + torch + GPU."""
    if not DIFFUSERS_AVAILABLE:
        raise ImportError(
            "diffusers/torch ne sont pas installés. Voir requirements-torch.txt. "
            "Sans cela, l'API utilise le générateur procédural de secours."
        )
    pipe = StableDiffusionPipeline.from_pretrained(base_model, torch_dtype=torch.float16)
    if lora_path:
        pipe.load_lora_weights(lora_path)
    pipe = pipe.to(device)
    return pipe
