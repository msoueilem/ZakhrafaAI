"""
Assistant de prompt DeepSeek — endpoints `/api/assist/*`.

  POST /api/assist/enhance  {prompt, category, lang}  -> {prompt}
  POST /api/assist/plan     {idea, lang}              -> {category, palette, engine, prompt, explanation}
  POST /api/assist/caption  {category, palette, lang} -> {caption}
  GET  /api/assist/status                             -> {enabled, model, remaining_today}

Erreurs : corps `{"code": "..."}` (codes machine, traduits par le frontend) :
  503 assist_disabled, 429 assist_ip_limit / assist_daily_limit (avec
  Retry-After), 502 assist_error ; 422 {detail, code: "validation", fields}
  (gestionnaire global de app.main).
La logique (prompts, quotas, cache, appels HTTP) vit dans services/deepseek.py.
"""
from __future__ import annotations

import logging
from typing import Annotated, Callable, Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

from app.services import deepseek, engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assist", tags=["assist"])

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1,
                                        max_length=deepseek.INPUT_MAX_LEN)]
Lang = Literal["fr", "ar", "en"]
Category = Literal[tuple(engine.VALID_CATEGORIES)]  # type: ignore[valid-type]
Palette = Literal[tuple(engine.VALID_PALETTES)]  # type: ignore[valid-type]
Engine = Literal[tuple(engine.VALID_ENGINES)]  # type: ignore[valid-type]


# ---------------------------------------------------------------------------
# Schémas
# ---------------------------------------------------------------------------

class EnhanceRequest(BaseModel):
    prompt: Text = Field(..., description="idée de style approximative (1-500 caractères)")
    category: Category
    lang: Lang = "fr"


class EnhanceResponse(BaseModel):
    prompt: str = Field(..., description="description précise pour le Rendu IA (≤ 300 caractères)")


class PlanRequest(BaseModel):
    idea: Text = Field(..., description="idée en langage naturel, fr/ar/en (1-500 caractères)")
    lang: Lang = "fr"


class PlanResponse(BaseModel):
    category: Category
    palette: Palette
    engine: Engine
    prompt: str = Field(..., description="souhait de style (≤ 300 caractères), vide si engine=gan")
    explanation: str = Field(..., description="justification courte (≤ 200 caractères)")


class CaptionRequest(BaseModel):
    category: Category
    palette: Palette
    lang: Lang = "fr"


class CaptionResponse(BaseModel):
    caption: str = Field(..., description="note culturelle (≤ 400 caractères)")


class StatusResponse(BaseModel):
    enabled: bool
    model: Optional[str] = None
    remaining_today: Optional[int] = None


class ErrorResponse(BaseModel):
    code: str = Field(..., description="assist_disabled | assist_ip_limit | assist_daily_limit | assist_error")


ERRORS = {503: {"model": ErrorResponse}, 429: {"model": ErrorResponse}, 502: {"model": ErrorResponse}}


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------

def client_ip(request: Request) -> Optional[str]:
    """Même règle que app.main.client_ip : le conteneur n'est joignable que
    via nginx en loopback, qui pose X-Real-IP ; à défaut, l'adresse de la socket."""
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip[:64]
    return request.client.host if request.client else None


def _guarded(call: Callable[[], dict]):
    """Traduit les échecs en `{"code": ...}` ; jamais de 500."""
    try:
        return call()
    except deepseek.AssistError as exc:
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        return JSONResponse(status_code=exc.status, content={"code": exc.code}, headers=headers)
    except Exception:
        logger.exception("Erreur inattendue dans l'assistant DeepSeek")
        return JSONResponse(status_code=502, content={"code": deepseek.CODE_ERROR})


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status", response_model=StatusResponse)
def status():
    return deepseek.get_assistant().status()


@router.post("/enhance", response_model=EnhanceResponse, responses=ERRORS)
def enhance(req: EnhanceRequest, request: Request):
    return _guarded(lambda: {"prompt": deepseek.get_assistant().enhance(
        prompt=req.prompt, category=req.category, lang=req.lang, client_ip=client_ip(request))})


@router.post("/plan", response_model=PlanResponse, responses=ERRORS)
def plan(req: PlanRequest, request: Request):
    return _guarded(lambda: deepseek.get_assistant().plan(
        idea=req.idea, lang=req.lang, client_ip=client_ip(request)))


@router.post("/caption", response_model=CaptionResponse, responses=ERRORS)
def caption(req: CaptionRequest, request: Request):
    return _guarded(lambda: {"caption": deepseek.get_assistant().caption(
        category=req.category, palette=req.palette, lang=req.lang, client_ip=client_ip(request))})
