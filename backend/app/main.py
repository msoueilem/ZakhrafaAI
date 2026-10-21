"""
ZakhrafaAI — API FastAPI.

Endpoints :
  GET  /api/health                 -> statut du service
  GET  /api/meta                   -> catégories / palettes / moteurs disponibles
  POST /api/generate               -> génère une image (voir GenerateRequest)
  GET  /api/dashboard              -> statistiques utilisateur (mock, cf. §7 tableau de bord)

Sert aussi le frontend statique (frontend/static) à la racine "/".
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services import engine

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend" / "static"

app = FastAPI(
    title="ZakhrafaAI",
    description="Génération de motifs artisanaux marocains par intelligence artificielle",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    category: str = Field(..., description="zellige | tapis | broderie")
    engine: str = Field("gan", description="gan | diffusion")
    palette: str = Field("zellige_classique")
    seed: Optional[int] = Field(None, description="graine aléatoire (bruit z); aléatoire si absente")
    size: Optional[int] = Field(None, description="taille de sortie en pixels (128-1024)")


class GenerateResponse(BaseModel):
    image: str
    engine: str
    source: str
    elapsed_ms: float
    seed: int
    width: int
    height: int


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
            {"id": "gan", "label": "GAN (rapide)", "default_resolution": 256},
            {"id": "diffusion", "label": "Diffusion (haute qualité)", "default_resolution": 768},
        ],
        "palettes": [
            {"id": "fes_bleu", "label": "Bleu de Fès"},
            {"id": "zellige_classique", "label": "Zellige classique"},
            {"id": "terracotta", "label": "Terracotta"},
            {"id": "emeraude", "label": "Émeraude"},
            {"id": "berbere", "label": "Berbère"},
            {"id": "monochrome_ivoire", "label": "Monochrome ivoire"},
        ],
    }


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    try:
        result = engine.generate(
            category=req.category,
            engine=req.engine,
            palette=req.palette,
            seed=req.seed,
            size=req.size,
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

    @app.get("/{page}.html")
    def page(page: str):
        target = FRONTEND_DIR / f"{page}.html"
        if not target.exists():
            raise HTTPException(status_code=404, detail="Page introuvable")
        return FileResponse(target)
