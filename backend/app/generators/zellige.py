"""Génération procédurale de motifs de zellige (mosaïque géométrique).

La seed pilote la structure (ordre des étoiles, finesse des branches,
disposition, rotation, motif de remplissage, schéma de couleurs) et pas
seulement les couleurs : deux seeds différentes donnent deux compositions
différentes, une même seed donne toujours la même image.
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
    regular_polygon,
    resolve_size,
    star_polygon,
)


def _choose_layout(rng: random.Random, engine: str) -> dict:
    """Tire les paramètres structurels de la composition à partir de la seed."""
    return {
        # moins de cellules en mode rapide, plus de répétitions en mode détaillé
        "cells": rng.choice([5, 6, 7]) if engine == "gan" else rng.choice([8, 9, 10]),
        "points": rng.choice([8, 8, 10, 12]),  # l'étoile à 8 branches reste la plus fréquente
        "inner_ratio": rng.uniform(0.36, 0.56),
        "outer_ratio": rng.uniform(0.46, 0.56),
        "offset_rows": rng.random() < 0.35,  # rangées décalées d'une demi-cellule
        "alternate_rotation": rng.random() < 0.5,  # rotation alternée en damier
        "filler": rng.choice(["croix", "losange", "etoile4"]),
        "center": rng.choice(["cabochon", "etoile", "rosace"]),
        "color_scheme": rng.choice(["damier", "anneaux", "diagonales"]),
    }


def _filler(draw, kind, mx, my, half, fill, outline):
    """Petite pièce posée entre les étoiles."""
    if kind == "croix":
        pts = [
            (mx, my - half), (mx + half * 0.4, my - half * 0.4),
            (mx + half, my), (mx + half * 0.4, my + half * 0.4),
            (mx, my + half), (mx - half * 0.4, my + half * 0.4),
            (mx - half, my), (mx - half * 0.4, my - half * 0.4),
        ]
    elif kind == "losange":
        pts = regular_polygon(mx, my, half, 4, rotation=0.0)
    else:  # étoile à 4 branches
        pts = star_polygon(mx, my, half, half * 0.35, 4, rotation=-math.pi / 2)
    draw.polygon(pts, fill=fill, outline=outline)


def generate(params: GenParams) -> Image.Image:
    rng = random.Random(params.seed)
    size = resolve_size(params.engine, params.size)
    palette = get_palette(params.palette)
    bg = palette[-1]
    grout = palette[-2]
    tiles = palette[:-1]

    img, draw = new_canvas(size, bg)
    lay = _choose_layout(rng, params.engine)

    cells = params.cells or lay["cells"]
    cell_size = size / cells
    r_outer = cell_size * lay["outer_ratio"]
    r_inner = r_outer * lay["inner_ratio"]
    points = lay["points"]
    base_rot = rng.choice([0.0, math.pi / points])  # pointe vers le haut ou à plat

    # Couleurs tirées une fois par composition, puis réparties de façon
    # symétrique (damier, anneaux concentriques, diagonales) comme sur un
    # panneau de zellige, au lieu d'une couleur aléatoire par étoile.
    order = tiles[:]
    rng.shuffle(order)
    star_cols = order[:2] if len(order) >= 2 else order * 2
    accent = order[2 % len(order)]
    filler_col = order[-1]
    center_r, center_c = cells / 2, cells / 2

    def star_color(row: int, col: int):
        scheme = lay["color_scheme"]
        if scheme == "damier":
            idx = (row + col) % 2
        elif scheme == "anneaux":
            idx = int(max(abs(row - center_r), abs(col - center_c))) % 2
        else:
            idx = ((row - col) // 2) % 2
        return star_cols[idx]

    jitter_rot = 0.03 if params.engine == "diffusion" else 0.08
    for row in range(cells + 1):
        x_shift = cell_size / 2 if (lay["offset_rows"] and row % 2) else 0.0
        for col in range(-1, cells + 1):
            cx = col * cell_size + x_shift
            cy = row * cell_size
            if cx < -r_outer or cx > size + r_outer:
                continue
            rotation = base_rot + rng.uniform(-jitter_rot, jitter_rot)
            if lay["alternate_rotation"] and (row + col) % 2:
                rotation += math.pi / points

            col_star = jitter_color(star_color(row, col), 10, rng)
            pts = star_polygon(cx, cy, r_outer, r_inner, points, rotation)
            draw.polygon(pts, fill=col_star, outline=jitter_color(grout, 8, rng))

            # pièce centrale de l'étoile
            dot_color = jitter_color(accent, 12, rng)
            dot_r = r_inner * 0.55
            if lay["center"] == "cabochon":
                draw.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=dot_color, outline=grout)
            elif lay["center"] == "etoile":
                draw.polygon(star_polygon(cx, cy, dot_r, dot_r * 0.5, points, rotation), fill=dot_color, outline=grout)
            else:  # rosace : polygone régulier + cœur
                draw.polygon(regular_polygon(cx, cy, dot_r, points, rotation), fill=dot_color, outline=grout)
                core = dot_r * 0.4
                draw.ellipse([cx - core, cy - core, cx + core, cy + core], fill=star_cols[0], outline=grout)

    # pièces de remplissage dans les vides entre étoiles : centre des cases en
    # grille droite, centres des triangles formés par trois étoiles en
    # disposition décalée (sinon elles chevaucheraient les branches).
    half = cell_size * (0.16 if lay["offset_rows"] else 0.22)
    for row in range(cells):
        for col in range(-1, cells + 1):
            if lay["offset_rows"]:
                s_top = cell_size / 2 if row % 2 else 0.0
                s_bot = cell_size / 2 if (row + 1) % 2 else 0.0
                spots = [
                    (col * cell_size + s_top + cell_size / 2, row * cell_size + cell_size / 3),
                    (col * cell_size + s_bot + cell_size / 2, row * cell_size + cell_size * 2 / 3),
                ]
            else:
                spots = [(col * cell_size + cell_size / 2, row * cell_size + cell_size / 2)]
            for mx, my in spots:
                if -half <= mx <= size + half:
                    _filler(draw, lay["filler"], mx, my, half, jitter_color(filler_col, 10, rng), grout)

    img = add_texture_noise(img, rng, strength=4.0 if params.engine == "diffusion" else 8.0)
    img = finish(img, params.engine)
    return img
