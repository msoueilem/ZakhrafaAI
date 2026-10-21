"""Génération procédurale de motifs de zellige (mosaïque géométrique)."""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw

from .utils import (
    GenParams,
    add_texture_noise,
    finish,
    get_palette,
    jitter_color,
    new_canvas,
    resolve_size,
    star_polygon,
)


def generate(params: GenParams) -> Image.Image:
    rng = random.Random(params.seed)
    size = resolve_size(params.engine, params.size)
    palette = get_palette(params.palette)
    bg = palette[-1]

    img, draw = new_canvas(size, bg)

    # Grille d'étoiles à 8 branches entrelacées avec croix, motif classique
    # du zellige de Fès. Le nombre de cellules dépend de l'engine : la
    # diffusion (haute résolution) permet plus de détail / répétitions.
    cells = 6 if params.engine == "gan" else 9
    cell_size = size / cells
    r_outer = cell_size * 0.52
    r_inner = r_outer * 0.42

    for row in range(cells + 1):
        for col in range(cells + 1):
            cx = col * cell_size
            cy = row * cell_size
            rotation = rng.uniform(-0.03, 0.03) if params.engine == "diffusion" else rng.uniform(-0.08, 0.08)

            star_color = jitter_color(rng.choice(palette[:-1]), 10, rng)
            pts = star_polygon(cx, cy, r_outer, r_inner, 8, rotation)
            draw.polygon(pts, fill=star_color, outline=jitter_color(palette[-2], 8, rng))

            # petite croix centrale (cabochon)
            dot_color = jitter_color(rng.choice(palette[:-1]), 12, rng)
            dot_r = r_inner * 0.5
            draw.ellipse(
                [cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r],
                fill=dot_color,
                outline=palette[-2],
            )

            # croix entre les étoiles (cases diagonales)
            if row < cells and col < cells:
                mx, my = cx + cell_size / 2, cy + cell_size / 2
                cross_color = jitter_color(rng.choice(palette[:-1]), 10, rng)
                half = cell_size * 0.22
                draw.polygon(
                    [
                        (mx, my - half), (mx + half * 0.4, my - half * 0.4),
                        (mx + half, my), (mx + half * 0.4, my + half * 0.4),
                        (mx, my + half), (mx - half * 0.4, my + half * 0.4),
                        (mx - half, my), (mx - half * 0.4, my - half * 0.4),
                    ],
                    fill=cross_color,
                    outline=palette[-2],
                )

    # fines lignes de jointure façon plâtre / ciment entre les tesselles
    grout = palette[-2]
    step = max(4, int(size / 64))
    for i in range(0, size, step):
        draw.line([(i, 0), (i, size)], fill=grout, width=1)

    img = add_texture_noise(img, rng, strength=4.0 if params.engine == "diffusion" else 8.0)
    img = finish(img, params.engine)
    return img
