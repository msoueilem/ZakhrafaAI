"""Génération procédurale de motifs de tapis (berbère / arabesque).

Composition en bandes horizontales, comme un tapis tissé : la seed choisit
le nombre de rangées, le motif de chaque bande (losange, losange emboîté,
losange à crochets, chevrons), le nombre de bordures et la symétrie
haut/bas. Une même seed donne toujours la même image.
"""
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

BAND_MOTIFS = ["losange", "losange_emboite", "losange_crochets", "chevrons"]


def _diamond(draw, cx, cy, rx, ry, fill, outline=None, width=1):
    pts = [(cx, cy - ry), (cx + rx, cy), (cx, cy + ry), (cx - rx, cy)]
    draw.polygon(pts, fill=fill, outline=outline, width=width)


def _band(draw, motif, x0, x1, y0, h, n, col_a, col_b, line, rng, lw):
    """Dessine une bande de `n` motifs entre x0 et x1, hauteur h."""
    w = (x1 - x0) / n
    cy = y0 + h / 2
    rx, ry = w * (0.34 if motif == "losange_crochets" else 0.42), h * 0.42
    if motif == "chevrons":
        # zigzag tissé : triangles alternés pleins, en deux couleurs
        # (2n - 1 triangles de largeur w décalés de w/2 : tiennent dans la bande)
        top, bot = y0 + h * 0.22, y0 + h * 0.78
        for i in range(n * 2 - 1):
            xa = x0 + i * w / 2
            col = col_a if i % 2 == 0 else col_b
            if i % 2 == 0:
                tri = [(xa, bot), (xa + w / 2, top), (xa + w, bot)]
            else:
                tri = [(xa, top), (xa + w / 2, bot), (xa + w, top)]
            draw.polygon(tri, fill=jitter_color(col, 8, rng), outline=line)
        return
    for i in range(n):
        cx = x0 + w * i + w / 2
        col = col_a if i % 2 == 0 else col_b
        other = col_b if i % 2 == 0 else col_a
        _diamond(draw, cx, cy, rx, ry, jitter_color(col, 8, rng), outline=line)
        if motif == "losange_emboite":
            for k, scale in enumerate((0.66, 0.36)):
                fill = other if k == 0 else col
                _diamond(draw, cx, cy, rx * scale, ry * scale, jitter_color(fill, 8, rng), outline=line)
        elif motif == "losange_crochets":
            # crochets berbères : ergots en équerre sur les pointes latérales
            hook = min(w / 2 - rx, ry * 0.5) * 0.9
            for sx in (-1, 1):
                tip = cx + sx * rx
                for sy in (-1, 1):
                    draw.line(
                        [(tip, cy), (tip + sx * hook, cy), (tip + sx * hook, cy + sy * hook)],
                        fill=col, width=lw * 2,
                    )
            _diamond(draw, cx, cy, rx * 0.35, ry * 0.35, jitter_color(other, 8, rng))
        else:  # losange simple, œil central
            draw.polygon(regular_polygon(cx, cy, min(rx, ry) * 0.4, 4), outline=other, width=lw)


def generate(params: GenParams) -> Image.Image:
    rng = random.Random(params.seed)
    size = resolve_size(params.engine, params.size)
    palette = get_palette(params.palette)
    bg = palette[0]
    motif_cols = palette[1:]
    line = palette[-1]

    img, draw = new_canvas(size, bg)
    lw = max(1, int(size / 256))

    # bordures encadrantes (2 à 4 filets) : la marge s'adapte à leur nombre
    n_borders = rng.randint(2, 4)
    w_border = max(2, int(size * 0.012))
    gap = max(2, int(size * 0.006))
    border = int(size * 0.025) + n_borders * (w_border + gap)
    border_cols = [rng.choice(motif_cols) for _ in range(n_borders)]
    for i, col in enumerate(border_cols):
        inset = int(size * 0.02) + i * (w_border + gap)
        draw.rectangle([inset, inset, size - 1 - inset, size - 1 - inset], outline=jitter_color(col, 6, rng), width=w_border)

    # champ central : bandes horizontales empilées, symétriques haut/bas
    # le plus souvent (composition régionale typique, §1.1)
    field = size - 2 * border
    rows = rng.choice([4, 5, 6]) if params.engine == "gan" else rng.choice([7, 8, 9, 10])
    per_row = rng.choice([rows - 1, rows, rows + 1]) if params.engine == "diffusion" else rng.choice([rows - 1, rows])
    mirrored = rng.random() < 0.75

    half = (rows + 1) // 2 if mirrored else rows
    plan = []
    for _ in range(half):
        a, b = rng.sample(motif_cols, 2) if len(motif_cols) >= 2 else (motif_cols[0], motif_cols[0])
        plan.append((rng.choice(BAND_MOTIFS), a, b))
    if mirrored:
        plan = plan + plan[: rows - half][::-1]

    band_h = field / rows
    sep = rng.choice(["dents", "filet", "aucun"])
    sep_col = rng.choice(motif_cols)
    for row, (motif, a, b) in enumerate(plan):
        y0 = border + band_h * row
        _band(draw, motif, border, size - border, y0, band_h, per_row, a, b, line, rng, lw)

        # séparateur entre bandes : filet simple ou filet bordé de dents
        if row < rows - 1 and sep != "aucun":
            y = y0 + band_h
            t = max(2, int(size * 0.005))
            draw.line([(border, y), (size - border, y)], fill=jitter_color(sep_col, 6, rng), width=t)
            if sep == "dents":
                step = field / (per_row * 4)
                x = border
                while x < size - border - step / 2:
                    draw.polygon([(x, y), (x + step / 2, y - step * 0.6), (x + step, y)], fill=sep_col)
                    x += step

    img = add_texture_noise(img, rng, strength=5.0 if params.engine == "diffusion" else 9.0)
    img = finish(img, params.engine)
    return img
