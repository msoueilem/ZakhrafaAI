"""
ZakhrafaAI — API FastAPI.

Endpoints :
  GET  /api/health                 -> statut du service
  GET  /api/meta                   -> catégories / palettes / moteurs / état du rendu IA
  POST /api/generate               -> génère une image (voir GenerateRequest)
  GET  /api/dashboard              -> statistiques globales du serveur (en mémoire, cf. §7)

Erreurs de validation (422, toutes routes) : `{"detail": ..., "code": "validation",
"fields": [noms des champs en cause]}` — `detail` reste la liste FastAPI
standard réduite à `loc`, `msg`, `type` (sans `input` ni `ctx`, qui
renverraient la saisie au client), ou un message pour les erreurs métier de
/api/generate.

Corps de requête > 64 Ko sur /api/* : 413 `{"code": "payload_too_large"}`
(Content-Length vérifié d'emblée, corps en flux plafonné à la lecture).

Sert aussi le frontend statique (frontend/static) à la racine "/".
"""
from __future__ import annotations

import base64
import io
import random
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from PIL import Image, features
from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.generators.utils import PALETTE_LABELS, PALETTES
from app.net import client_ip
from app.routers import assist
from app.services import deepseek, engine, gemini

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
# ---------------------------------------------------------------------------
# Taille maximale des corps de requête (/api/*)
# ---------------------------------------------------------------------------

MAX_BODY_BYTES = 64 * 1024
PAYLOAD_TOO_LARGE = {"code": "payload_too_large"}


class PayloadTooLarge(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=413, detail="payload_too_large")


class BodySizeLimitMiddleware:
    """Middleware ASGI : refuse en 413 un corps de plus de `max_bytes` sur
    /api/*. Content-Length est vérifié avant d'appeler l'application ; un
    corps en flux (chunked) est compté à la lecture et interrompu dès le
    dépassement (PayloadTooLarge, traduit en 413 par le gestionnaire)."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES, prefix: str = "/api/"):
        self.app = app
        self.max_bytes = max_bytes
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith(self.prefix):
            return await self.app(scope, receive, send)

        for name, value in scope.get("headers") or ():
            if name == b"content-length":
                try:
                    too_large = int(value) > self.max_bytes
                except ValueError:
                    too_large = False
                if too_large:
                    response = JSONResponse(status_code=413, content=PAYLOAD_TOO_LARGE)
                    return await response(scope, receive, send)

        received = 0
        started = False

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise PayloadTooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except PayloadTooLarge:
            if started:
                raise
            response = JSONResponse(status_code=413, content=PAYLOAD_TOO_LARGE)
            await response(scope, receive, send)


@app.exception_handler(PayloadTooLarge)
async def _on_payload_too_large(request: Request, exc: PayloadTooLarge):
    return JSONResponse(status_code=413, content=PAYLOAD_TOO_LARGE)


# ajouté avant CORS : CORS reste la couche externe (en-têtes sur le 413 aussi)
app.add_middleware(BodySizeLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# assistant de prompt DeepSeek (/api/assist/*)
app.include_router(assist.router)


# ---------------------------------------------------------------------------
# Erreurs de validation : code machine + champs en cause
# ---------------------------------------------------------------------------

_LOC_ROOTS = {"body", "query", "path", "header", "cookie"}


def _fields_from_errors(errors) -> List[str]:
    """Noms des champs (1er niveau) cités par les erreurs pydantic, sans doublon."""
    fields: List[str] = []
    for err in errors:
        loc = [part for part in err.get("loc", ()) if isinstance(part, str)]
        if loc and loc[0] in _LOC_ROOTS:
            loc = loc[1:]
        if loc and loc[0] not in fields:
            fields.append(loc[0])
    return fields


_ERROR_KEYS = ("loc", "msg", "type")


def _public_errors(errors) -> List[dict]:
    """Erreurs pydantic sans `input` ni `ctx` (ni `url`) : la saisie du client
    ne lui est jamais renvoyée."""
    return [{k: err[k] for k in _ERROR_KEYS if k in err} for err in errors]


def validation_error(detail: Any, fields: List[str]) -> JSONResponse:
    return JSONResponse(status_code=422, content={
        "detail": jsonable_encoder(detail), "code": "validation", "fields": fields})


@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    return validation_error(_public_errors(errors), _fields_from_errors(errors))


MAX_SEED = 2**53 - 1

# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    category: str = Field(..., description="zellige | tapis | broderie")
    engine: str = Field("gan", description="gan (rapide, procédural, 256px) | diffusion (rendu IA Gemini, 768px, repli procédural)")
    palette: str = Field("zellige_classique")
    # Bornée à 2**53 - 1 (Number.MAX_SAFE_INTEGER) : au-delà, un navigateur ne
    # relit pas la seed renvoyée à l'identique et « Régénérer » changerait d'image.
    seed: Optional[int] = Field(None, ge=0, le=MAX_SEED,
                                description="graine aléatoire (bruit z), entier 0..2**53-1 ; aléatoire si absente")
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
    # phrase française fixe par notice_code (rétrocompatibilité) ; jamais le
    # texte d'erreur du service amont (cf. gemini.NOTICES)
    notice: Optional[str] = None
    # code machine du repli IA, traduit par le frontend :
    # ai_disabled | daily_limit | ip_limit | timeout | blocked | service_error
    notice_code: Optional[str] = None
    notice_params: Dict[str, Any] = Field(default_factory=dict)  # ex. {"n": 30}


class HistoryItem(BaseModel):
    id: str
    category: str
    engine: str
    source: str  # procedural | gemini | trained_weights
    date: str  # ISO 8601 UTC, ex. « 2026-10-23T01:33:00Z »
    seed: int
    palette: str
    thumb: Optional[str] = None  # data URL WebP (ou JPEG) 160x160


# ---------------------------------------------------------------------------
# état "session" en mémoire pour le tableau de bord (démo, non persistant)
# ---------------------------------------------------------------------------

RECENT_MAX = 8
THUMB_SIZE = 160
THUMB_QUALITY = 70
_THUMB_FORMAT = "WEBP" if features.check("webp") else "JPEG"

_HISTORY: List[dict] = []  # RECENT_MAX dernières générations (avec vignette)
# compteurs cumulés depuis le démarrage (indépendants de la taille de _HISTORY)
_TOTALS: Dict[str, Counter] = {"category": Counter(), "engine": Counter(), "source": Counter()}
_STATS_LOCK = threading.Lock()


def reset_stats() -> None:
    with _STATS_LOCK:
        _HISTORY.clear()
        for counter in _TOTALS.values():
            counter.clear()


def make_thumb(img: Image.Image) -> str:
    """Vignette légère (data URL) pour le tableau de bord."""
    thumb = img.convert("RGB")
    thumb.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.BILINEAR, reducing_gap=2.0)
    buf = io.BytesIO()
    thumb.save(buf, format=_THUMB_FORMAT, quality=THUMB_QUALITY)
    mime = "image/webp" if _THUMB_FORMAT == "WEBP" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


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
        # état de l'assistant DeepSeek (même contenu que /api/assist/status)
        "assist": deepseek.get_assistant().status(),
    }


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
        fields = [exc.field] if isinstance(exc, engine.InvalidParam) else []
        return validation_error(str(exc), fields)

    # date en UTC explicite : le tableau de bord l'affiche à l'heure locale du navigateur
    entry = {
        "id": f"{req.category}_{int(time.time() * 1000)}_{random.randint(100,999)}",
        "category": req.category,
        "engine": req.engine,
        "source": result.source,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": result.seed,
        "palette": result.palette or req.palette,
        "thumb": make_thumb(result.image),
    }
    with _STATS_LOCK:
        _TOTALS["category"][req.category] += 1
        _TOTALS["engine"][req.engine] += 1
        _TOTALS["source"][result.source] += 1
        _HISTORY.insert(0, entry)
        del _HISTORY[RECENT_MAX:]

    return result.to_dict()


@app.get("/api/dashboard")
def dashboard():
    """Totaux cumulés depuis le démarrage du serveur ; `derniers_motifs` :
    les RECENT_MAX dernières générations, avec vignette."""
    with _STATS_LOCK:
        counts = {k: _TOTALS["category"][k] for k in ("zellige", "tapis", "broderie")}
        engines = {k: _TOTALS["engine"][k] for k in ("gan", "diffusion")}
        # source réelle : en rendu IA, « procedural » signifie un repli
        sources = {k: _TOTALS["source"][k] for k in ("procedural", "gemini", "trained_weights")}
        total = sum(_TOTALS["category"].values())
        recent = [dict(h) for h in _HISTORY[:RECENT_MAX]]
    return {
        "total_motifs": total,
        "repartition_par_categorie": counts,
        "repartition_par_moteur": engines,
        "repartition_par_source": sources,
        "derniers_motifs": recent,
    }


# ---------------------------------------------------------------------------
# Frontend statique
# ---------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")

    # HEAD en plus de GET (sondes de disponibilité, aperçus de liens) ;
    # FileResponse n'envoie alors que les en-têtes.
    PAGE_METHODS = ["GET", "HEAD"]

    @app.api_route("/", methods=PAGE_METHODS)
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    # URLs propres (/studio) ; les anciennes en .html redirigent en 301
    PAGES = {"studio", "dashboard"}

    @app.api_route("/{page}.html", methods=PAGE_METHODS)
    def legacy_page(page: str):
        if page == "index":
            return RedirectResponse("/", status_code=301)
        if page in PAGES:
            return RedirectResponse(f"/{page}", status_code=301)
        raise HTTPException(status_code=404, detail="Page introuvable")

    # « /studio/ » : sans cette route, Starlette redirigeait (307) vers une
    # URL absolue reconstruite côté conteneur, donc en http:// derrière nginx.
    # Redirection explicite, permanente et relative (le schéma est conservé).
    @app.api_route("/{page}/", methods=PAGE_METHODS)
    def page_trailing_slash(page: str):
        if page not in PAGES:
            raise HTTPException(status_code=404, detail="Page introuvable")
        return RedirectResponse(f"/{page}", status_code=301)

    @app.api_route("/{page}", methods=PAGE_METHODS)
    def page(page: str):
        if page not in PAGES:
            raise HTTPException(status_code=404, detail="Page introuvable")
        return FileResponse(FRONTEND_DIR / f"{page}.html")
