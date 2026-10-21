"""Génération procédurale de motifs de tapis (berbère / arabesque)."""
from __future__ import annotations

import random

from PIL import Image, ImageDraw

from .utils import (
    GenParams,
    add_texture_noise,
    finish,
    get_palette,
    jitter_color,
    new_canvas,
    regular_polygon,
    resolve_size,
)


def generate(params: GenParams) -> Image.Image:
    rng = random.Random(params.seed)
    size = resolve_size(params.engine, params.size)
    palette = get_palette(params.palette)
    bg = palette[0]

    img, draw = new_canvas(size, bg)

    border = int(size * 0.06)
    # bordure encadrante (composition régionale typique)
    for i in range(3):
        col = jitter_color(rng.choice(palette[1:]), 8, rng)
        w = int(size * 0.015)
        inset = border - i * (w + 2)
        draw.rectangle([inset, inset, size - inset, size - inset], outline=col, width=w)

    # champ central : losanges empilés (motif tribal berbère)
    field = size - 2 * border
    rows = 5 if params.engine == "gan" else 8
    cell = field / rows
    cy0 = border

    for row in range(rows):
        cy = cy0 + cell * row + cell / 2
        cols = rows
        for col in range(cols):
            cx = border + cell * col + cell / 2
            diamond_color = jitter_color(rng.choice(palette[1:]), 10, rng)
            r = cell * rng.uniform(0.32, 0.42)
            pts = regular_polygon(cx, cy, r, 4, rotation=0.0)  # losange (carré tourné à 45°)
            draw.polygon(pts, fill=diamond_color, outline=palette[-1])

            # motif interne en zigzag (crochets berbères)
            hook_color = jitter_color(rng.choice(palette[1:]), 14, rng)
            small_r = r * 0.4
            draw.polygon(
                regular_polygon(cx, cy, small_r, 4, rotation=0.0),
                outline=hook_color,
                width=max(1, int(size / 256)),
            )

    # bandes horizontales décoratives (compositions régionales, §1.1)
    n_bands = 3 if params.engine == "gan" else 5
    for b in range(n_bands):
        y = border + (field / (n_bands + 1)) * (b + 1)
        band_color = jitter_color(rng.choice(palette[1:]), 10, rng)
        thickness = max(2, int(size * 0.006))
        draw.line([(border, y), (size - border, y)], fill=band_color, width=thickness)
        # petits triangles le long de la bande
        step = field / rows
        x = border
        while x < size - border:
            tri_color = jitter_color(rng.choice(palette[1:]), 10, rng)
            draw.polygon(
                [(x, y - thickness), (x + step * 0.25, y), (x, y + thickness)],
                fill=tri_color,
            )
            x += step * 0.5

    img = add_texture_noise(img, rng, strength=5.0 if params.engine == "diffusion" else 9.0)
    img = finish(img, params.engine)
    return img
