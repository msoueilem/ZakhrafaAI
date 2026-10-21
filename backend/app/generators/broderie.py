"""Génération procédurale de motifs de broderie (ornements floraux/géométriques)."""
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
)


def _flower(draw: ImageDraw.ImageDraw, cx, cy, r, petals, color, center_color, rng, width):
    for i in range(petals):
        angle = 2 * math.pi * i / petals
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        petal_color = jitter_color(color, 10, rng)
        draw.ellipse(
            [px - r * 0.45, py - r * 0.45, px + r * 0.45, py + r * 0.45],
            outline=petal_color,
            width=width,
        )
    draw.ellipse([cx - r * 0.28, cy - r * 0.28, cx + r * 0.28, cy + r * 0.28], fill=center_color)


def generate(params: GenParams) -> Image.Image:
    rng = random.Random(params.seed)
    size = resolve_size(params.engine, params.size)
    palette = get_palette(params.palette)
    bg = palette[-1] if params.engine == "gan" else palette[2] if len(palette) > 2 else palette[-1]

    img, draw = new_canvas(size, bg)

    grid = 4 if params.engine == "gan" else 6
    cell = size / grid
    line_w = max(1, int(size / 220))

    for row in range(grid):
        for col in range(grid):
            cx = cell * col + cell / 2
            cy = cell * row + cell / 2
            r = cell * rng.uniform(0.28, 0.38)
            petals = rng.choice([5, 6, 8])
            color = rng.choice(palette[:-1])
            center = jitter_color(rng.choice(palette[:-1]), 15, rng)
            _flower(draw, cx, cy, r, petals, color, center, rng, line_w)

            # tiges / feuilles reliant les motifs floraux (arabesque)
            if col < grid - 1:
                mx = cx + cell / 2
                my = cy + rng.uniform(-cell * 0.1, cell * 0.1)
                leaf_color = jitter_color(rng.choice(palette[:-1]), 12, rng)
                draw.line([(cx + r, cy), (mx, my), (mx + r, my)], fill=leaf_color, width=line_w)
                leaf_r = cell * 0.08
                draw.ellipse(
                    [mx - leaf_r, my - leaf_r * 1.6, mx + leaf_r, my + leaf_r * 0.4],
                    outline=leaf_color,
                    width=line_w,
                )
            if row < grid - 1:
                mx = cx + rng.uniform(-cell * 0.1, cell * 0.1)
                my = cy + cell / 2
                leaf_color = jitter_color(rng.choice(palette[:-1]), 12, rng)
                draw.line([(cx, cy + r), (mx, my), (mx, my + r)], fill=leaf_color, width=line_w)

    img = add_texture_noise(img, rng, strength=4.0 if params.engine == "diffusion" else 7.0)
    img = finish(img, params.engine)
    return img
