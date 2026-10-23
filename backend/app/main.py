"""
ZakhrafaAI — API FastAPI.

Endpoints :
  GET  /api/health                 -> statut du service
  GET  /api/meta                   -> catégories / palettes / moteurs / état du rendu IA
  POST /api/generate               -> génère une image (voir GenerateRequest)
  GET  /api/dashboard              -> statistiques globales du serveur (en mémoire, cf. §7)

Sert aussi le frontend statique (frontend/static) à la racine "/".
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.generators.utils import PALETTE_LABELS, PALETTES
from app.services import engine, gemini

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend" / "static"

app = FastAPI(
    title="ZakhrafaAI",
    description="Génération de motifs artisanaux marocains par intelligence artificielle",
    version="1.0.0",
)

# Le frontend est servi par la même origine : CORS n'est utile que pour
# appeler l'API depuis un autre site. Ouvert, mais sans cookies/identifiants
# (« * » + credentials est refusé par les navigateurs et serait dangereux).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    category: str = Field(..., description="zellige | tapis | broderie")
    engine: str = Field("gan", description="gan (rapide, procédural, 256px) | diffusion (rendu IA Gemini, 768px, repli procédural)")
    palette: str = Field("zellige_classique")
    seed: Optional[int] = Field(None, description="graine aléatoire (bruit z); aléatoire si absente")
    size: Optional[int] = Field(None, description="taille de sortie en pixels (128-1024)")
    prompt: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=gemini.PROMPT_MAX_LEN)]] = Field(
        None, description="souhait de style libre (rendu IA uniquement, 300 caractères max)")

    @field_validator("prompt")
    @classmethod
    def _empty_prompt_is_none(cls, v: Optional[str]) -> Optional[str]:
        return v or None


class GenerateResponse(BaseModel):
    image: str
    engine: str
    source: str
    elapsed_ms: float
    seed: int
    width: int
    height: int
    model: Optional[str] = None
    notice: Optional[str] = None


class HistoryItem(BaseModel):
    id: str
    category: str
    engine: str
    date: str


# ---------------------------------------------------------------------------
# état "session" en mémoire pour le tableau de bord (démo, non persistant)
# ---------------------------------------------------------------------------

_HISTORY: List[dict] = []


# ---------------------------------------------------------------------------
# Routes API
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok", "app": "ZakhrafaAI"}


@app.get("/api/meta")
def meta():
    return {
        "categories": [
            {"id": "zellige", "label": "Zellige", "complexity": "Haute"},
            {"id": "tapis", "label": "Tapis", "complexity": "Moyenne à élevée"},
            {"id": "broderie", "label": "Broderie", "complexity": "Moyenne"},
        ],
        "engines": [
            # ids historiques conservés pour compatibilité : « gan » est
            # procédural (sauf poids GAN fournis), « diffusion » est le rendu
            # IA hybride (géométrie procédurale + rendu Gemini).
            {"id": "gan", "label": "Rapide (procédural)", "default_resolution": 256},
            {"id": "diffusion", "label": "Rendu IA (Gemini)", "default_resolution": 768},
        ],
        # état du rendu IA (la clé n'est jamais exposée)
        "ai": gemini.get_renderer().status(),
        # couleurs réelles (source unique : generators/utils.PALETTES) pour
        # afficher chaque palette telle qu'elle sera rendue
        "palettes": [
            {"id": pid, "label": PALETTE_LABELS.get(pid, pid), "colors": colors}
            for pid, colors in PALETTES.items()
        ],
    }


def client_ip(request: Request) -> Optional[str]:
    """Le conteneur n'est joignable que via nginx en loopback, qui pose
    X-Real-IP ; à défaut (lancement direct), l'adresse de la socket."""
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip[:64]
    return request.client.host if request.client else None


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest, request: Request):
    try:
        result = engine.generate(
            category=req.category,
            engine=req.engine,
            palette=req.palette,
            seed=req.seed,
            size=req.size,
            prompt=req.prompt,
            client_ip=client_ip(request),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    entry = {
        "id": f"{req.category}_{int(time.time() * 1000)}_{random.randint(100,999)}",
        "category": req.category,
        "engine": req.engine,
        "date": time.strftime("%Y-%m-%d %H:%M"),
    }
    _HISTORY.insert(0, entry)
    del _HISTORY[50:]

    return result.to_dict()


@app.get("/api/dashboard")
def dashboard():
    counts = {"zellige": 0, "tapis": 0, "broderie": 0}
    for h in _HISTORY:
        if h["category"] in counts:
            counts[h["category"]] += 1
    return {
        "total_motifs": len(_HISTORY),
        "repartition_par_categorie": counts,
        "derniers_motifs": _HISTORY[:8],
    }


# ---------------------------------------------------------------------------
# Frontend statique
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    # URLs propres (/studio) ; les anciennes en .html redirigent en 301
    PAGES = {"studio", "dashboard"}

    @app.get("/{page}.html")
    def legacy_page(page: str):
        if page == "index":
            return RedirectResponse("/", status_code=301)
        if page in PAGES:
            return RedirectResponse(f"/{page}", status_code=301)
        raise HTTPException(status_code=404, detail="Page introuvable")

    @app.get("/{page}")
    def page(page: str):
        if page not in PAGES:
            raise HTTPException(status_code=404, detail="Page introuvable")
        return FileResponse(FRONTEND_DIR / f"{page}.html")
