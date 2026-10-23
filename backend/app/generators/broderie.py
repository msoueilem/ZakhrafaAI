"""Génération procédurale de motifs de broderie (ornements floraux/géométriques).

La seed choisit la grille, le nombre de pétales (alternés en damier), le
style de rosace (pétales cerclés, pétales pleins en amande, rosace rayonnante
ou point de croix façon broderie de Fès) et le style des tiges qui relient
les rosaces. Une même seed donne toujours la même image.
"""
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

ROSETTE_STYLES = ["contour", "amande", "rayonnante", "point_de_croix"]


def _flower(draw: ImageDraw.ImageDraw, cx, cy, r, petals, color, center_color, rng, width):
    """Rosace à pétales cerclés (style d'origine)."""
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


def _almond_flower(draw, cx, cy, r, petals, color, center_color, rng, width, rotation):
    """Rosace à pétales pleins en amande (pointus aux deux extrémités)."""
    for i in range(petals):
        a = 2 * math.pi * i / petals + rotation
        perp = a + math.pi / 2
        bulge = r * math.sin(math.pi / petals) * 0.8
        mid = (cx + r * 0.55 * math.cos(a), cy + r * 0.55 * math.sin(a))
        pts = [
            (cx + r * 0.12 * math.cos(a), cy + r * 0.12 * math.sin(a)),
            (mid[0] + bulge * math.cos(perp), mid[1] + bulge * math.sin(perp)),
            (cx + r * 1.05 * math.cos(a), cy + r * 1.05 * math.sin(a)),
            (mid[0] - bulge * math.cos(perp), mid[1] - bulge * math.sin(perp)),
        ]
        draw.polygon(pts, fill=jitter_color(color, 10, rng), outline=center_color, width=max(1, width // 2))
    cr = r * 0.22
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=center_color)


def _radiant_flower(draw, cx, cy, r, petals, color, center_color, rng, width, rotation):
    """Rosace rayonnante : rayons + couronne de points (point de tige / point lancé)."""
    for i in range(petals * 2):
        a = math.pi * i / petals + rotation
        length = r if i % 2 == 0 else r * 0.6
        draw.line([(cx, cy), (cx + length * math.cos(a), cy + length * math.sin(a))],
                  fill=jitter_color(color, 10, rng), width=width)
        if i % 2 == 0:
            d = r * 0.12
            ex, ey = cx + length * math.cos(a), cy + length * math.sin(a)
            draw.ellipse([ex - d, ey - d, ex + d, ey + d], fill=center_color)
    draw.ellipse([cx - r * 0.5, cy - r * 0.5, cx + r * 0.5, cy + r * 0.5], outline=color, width=width)
    cr = r * 0.2
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=center_color)


def _cross_stitch(draw, cx, cy, r, petals, color, center_color, width, stitches):
    """Rosace géométrique en point de croix (broderie de Fès, « terz fassi ») :
    une étoile discrétisée en petites croix sur une grille."""
    s = 2 * r / stitches
    k = 4 if petals % 4 == 0 else 2  # étoile à 8 branches ou losange
    for i in range(stitches):
        for j in range(stitches):
            u = (i + 0.5) / stitches * 2 - 1
            v = (j + 0.5) / stitches * 2 - 1
            diamond = abs(u) + abs(v)
            square = max(abs(u), abs(v))
            inside = diamond <= 1.0 if k == 2 else min(diamond, square * 1.45) <= 1.0
            if not inside:
                continue
            ring = diamond if k == 2 else min(diamond, square * 1.45)
            col = center_color if ring < 0.35 or 0.62 < ring < 0.78 else color
            x, y = cx - r + i * s, cy - r + j * s
            pad = s * 0.15
            draw.line([(x + pad, y + pad), (x + s - pad, y + s - pad)], fill=col, width=width)
            draw.line([(x + s - pad, y + pad), (x + pad, y + s - pad)], fill=col, width=width)


def _leaf(x, y, length, angle):
    """Feuille en amande partant de (x, y) dans la direction `angle`."""
    tip = (x + length * math.cos(angle), y + length * math.sin(angle))
    mid = (x + length * 0.5 * math.cos(angle), y + length * 0.5 * math.sin(angle))
    w = length * 0.28
    perp = angle + math.pi / 2
    return [
        (x, y),
        (mid[0] + w * math.cos(perp), mid[1] + w * math.sin(perp)),
        tip,
        (mid[0] - w * math.cos(perp), mid[1] - w * math.sin(perp)),
    ]


def generate(params: GenParams) -> Image.Image:
    rng = random.Random(params.seed)
    size = resolve_size(params.engine, params.size)
    palette = get_palette(params.palette)
    bg = palette[-1] if params.engine == "gan" else palette[2] if len(palette) > 2 else palette[-1]
    inks = [c for c in palette if c != bg]

    img, draw = new_canvas(size, bg)

    grid = rng.choice([3, 4, 5]) if params.engine == "gan" else rng.choice([5, 6, 7])
    cell = size / grid
    line_w = max(1, int(size / 220))
    style = rng.choice(ROSETTE_STYLES)
    petal_pair = (rng.choice([5, 6, 8]), rng.choice([6, 8, 10, 12]))
    vine = rng.choice(["droite", "ondulee", "aucune"]) if style != "point_de_croix" else rng.choice(["droite", "aucune"])
    radius_ratio = rng.uniform(0.28, 0.38)
    rotation = rng.uniform(0, math.pi)

    # deux jeux de couleurs alternés en damier : répétition symétrique typique
    col_a, col_b, col_c = (rng.sample(inks, 3) if len(inks) >= 3 else (inks * 3)[:3])
    stitches = 9 if params.engine == "gan" else 13

    for row in range(grid):
        for col in range(grid):
            cx = cell * col + cell / 2
            cy = cell * row + cell / 2
            checker = (row + col) % 2
            r = cell * radius_ratio
            petals = petal_pair[checker]
            color = col_a if checker == 0 else col_b
            center = jitter_color(col_c, 15, rng)

            if style == "contour":
                _flower(draw, cx, cy, r, petals, color, center, rng, line_w)
            elif style == "amande":
                _almond_flower(draw, cx, cy, r, petals, color, center, rng, line_w, rotation)
            elif style == "rayonnante":
                _radiant_flower(draw, cx, cy, r, petals, color, center, rng, line_w, rotation)
            else:
                _cross_stitch(draw, cx, cy, r * 1.15, petals, color, center, line_w, stitches)

            if vine == "aucune":
                continue
            # tiges / feuilles reliant les motifs floraux (arabesque)
            leaf_color = jitter_color(col_c, 12, rng)
            if col < grid - 1:
                mx, my = cx + cell / 2, cy
                if vine == "ondulee":
                    my = cy - cell * 0.12 if checker else cy + cell * 0.12  # sommet de l'arc
                    bbox = [cx + r, cy - cell * 0.12, cx + cell - r, cy + cell * 0.12]
                    draw.arc(bbox, 180 if checker else 0, 360 if checker else 180, fill=leaf_color, width=line_w)
                else:
                    draw.line([(cx + r * 1.1, cy), (cx + cell - r * 1.1, cy)], fill=leaf_color, width=line_w)
                # paire de feuilles en amande, inclinées de part et d'autre de la tige
                for a in (-math.pi / 4, math.pi / 4):
                    draw.polygon(_leaf(mx, my, cell * 0.11, a), fill=leaf_color)
            if row < grid - 1:
                draw.line([(cx, cy + r * 1.1), (cx, cy + cell - r * 1.1)], fill=leaf_color, width=line_w)

    img = add_texture_noise(img, rng, strength=4.0 if params.engine == "diffusion" else 7.0)
    img = finish(img, params.engine)
    return img
