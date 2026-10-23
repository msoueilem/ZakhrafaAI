"""Tests de l'API ZakhrafaAI (générateur procédural, sans poids entraînés)."""
from __future__ import annotations

import numpy as np
import pytest

from app.generators import utils
from app.services import engine

from .helpers import decode_png

CATEGORIES = ["zellige", "tapis", "broderie"]
ENGINES = {"gan": 256, "diffusion": 768}


def gen(client, **payload):
    body = {"category": "zellige", "engine": "gan", "palette": "fes_bleu", **payload}
    return client.post("/api/generate", json=body)


# --- santé / métadonnées ---------------------------------------------------

def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "app": "ZakhrafaAI"}


def test_meta_lists_categories_engines_palettes(client):
    data = client.get("/api/meta").json()
    assert [c["id"] for c in data["categories"]] == CATEGORIES
    assert {e["id"]: e["default_resolution"] for e in data["engines"]} == ENGINES
    assert {p["id"] for p in data["palettes"]} == set(engine.VALID_PALETTES)


# --- génération -------------------------------------------------------------

@pytest.mark.parametrize("category", CATEGORIES)
@pytest.mark.parametrize("engine_id", list(ENGINES))
def test_generate_all_combinations(client, category, engine_id):
    res = gen(client, category=category, engine=engine_id, seed=123)
    assert res.status_code == 200
    data = res.json()
    size = ENGINES[engine_id]
    assert (data["width"], data["height"]) == (size, size)
    assert data["engine"] == engine_id
    assert data["source"] == "procedural"
    assert data["seed"] == 123
    img = decode_png(data["image"])
    assert img.size == (size, size)
    assert img.mode == "RGB"


def test_random_seed_is_returned_and_reproduces(client):
    first = gen(client).json()
    assert isinstance(first["seed"], int)
    again = gen(client, seed=first["seed"]).json()
    assert again["image"] == first["image"]


@pytest.mark.parametrize("category", CATEGORIES)
def test_same_seed_gives_identical_image(client, category):
    a = gen(client, category=category, seed=42).json()["image"]
    b = gen(client, category=category, seed=42).json()["image"]
    assert a == b


@pytest.mark.parametrize("category", CATEGORIES)
def test_different_seeds_give_different_images(client, category):
    a = gen(client, category=category, seed=1).json()["image"]
    b = gen(client, category=category, seed=2).json()["image"]
    assert a != b


@pytest.mark.parametrize("category", CATEGORIES)
def test_seed_changes_structure_not_only_colors(category, monkeypatch):
    """Rendu en silhouette : toutes les encres ont la même couleur (noir) et
    seul le fond est blanc, donc la répartition des couleurs n'a plus aucun
    effet. Si deux seeds donnent des silhouettes nettement différentes, c'est
    bien la géométrie (structure) qui varie."""
    ink, paper = "#000000", "#FFFFFF"
    # le fond est palette[0] pour le tapis, palette[-1] pour zellige/broderie (mode gan)
    sil = [paper] + [ink] * 4 if category == "tapis" else [ink] * 4 + [paper]
    monkeypatch.setitem(utils.PALETTES, "silhouette", sil)

    def mask(seed):
        params = utils.GenParams(category=category, engine="gan", palette="silhouette", seed=seed)
        img = np.asarray(engine.GENERATORS[category].generate(params).convert("L"))
        return img < 128

    # Le simple « bruit » géométrique (petites rotations, rayons tirés au
    # hasard) de l'ancien générateur restait sous ~16 % ; un vrai changement
    # de composition (grille, motifs, styles) dépasse largement 25 %.
    base = mask(1)
    diffs = [(base != mask(s)).mean() for s in range(2, 11)]
    assert max(diffs) > 0.25, diffs


@pytest.mark.parametrize("requested, expected", [(50, 128), (128, 128), (300, 300), (5000, 1024)])
def test_size_is_clamped(client, requested, expected):
    data = gen(client, size=requested, seed=5).json()
    assert (data["width"], data["height"]) == (expected, expected)
    assert decode_png(data["image"]).size == (expected, expected)


def test_unknown_palette_falls_back(client):
    res = gen(client, palette="inexistante", seed=9)
    assert res.status_code == 200
    assert res.json()["image"] == gen(client, palette="zellige_classique", seed=9).json()["image"]


# --- validation --------------------------------------------------------------

def test_bad_category_is_422(client):
    res = gen(client, category="poterie")
    assert res.status_code == 422
    assert "category" in res.json()["detail"]


def test_bad_engine_is_422(client):
    res = gen(client, engine="vae")
    assert res.status_code == 422
    assert "engine" in res.json()["detail"]


def test_missing_category_is_422_with_list_detail(client):
    res = client.post("/api/generate", json={"engine": "gan"})
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)


def test_wrong_seed_type_is_422(client):
    assert gen(client, seed="abc").status_code == 422


# --- tableau de bord ---------------------------------------------------------

def test_dashboard_empty(client):
    data = client.get("/api/dashboard").json()
    assert data["total_motifs"] == 0
    assert data["repartition_par_categorie"] == {"zellige": 0, "tapis": 0, "broderie": 0}
    assert data["derniers_motifs"] == []


def test_dashboard_counts(client):
    for cat in ["zellige", "zellige", "tapis", "broderie", "broderie", "broderie"]:
        assert gen(client, category=cat, seed=1).status_code == 200
    gen(client, category="poterie")  # échec : ne doit pas être compté

    data = client.get("/api/dashboard").json()
    assert data["total_motifs"] == 6
    assert data["repartition_par_categorie"] == {"zellige": 2, "tapis": 1, "broderie": 3}
    assert len(data["derniers_motifs"]) == 6
    assert data["derniers_motifs"][0]["category"] == "broderie"
    assert data["derniers_motifs"][-1]["category"] == "zellige"


def test_dashboard_lists_at_most_8_recent(client):
    for i in range(10):
        gen(client, seed=i)
    data = client.get("/api/dashboard").json()
    assert data["total_motifs"] == 10
    assert len(data["derniers_motifs"]) == 8


# --- frontend statique ---------------------------------------------------------

@pytest.mark.parametrize("path", ["/", "/index.html", "/studio.html", "/dashboard.html",
                                  "/assets/css/styles.css", "/assets/js/api.js",
                                  "/assets/js/studio.js", "/assets/js/dashboard.js"])
def test_static_pages(client, path):
    assert client.get(path).status_code == 200


def test_unknown_page_is_404(client):
    assert client.get("/inexistante.html").status_code == 404
