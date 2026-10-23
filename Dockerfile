# ZakhrafaAI — image de production (procédural + rendu IA Gemini, sans torch)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ZAKHRAFAAI_DATA_DIR=/data

# main.py sert ../frontend/static relativement à backend/ : on garde la même
# arborescence (/app/backend + /app/frontend).
WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin zakhrafa \
    && mkdir -p /data && chown zakhrafa:zakhrafa /data

# compteur journalier des rendus IA (volume nommé dans docker-compose)
VOLUME ["/data"]

COPY --chown=root:root backend/ /app/backend/
COPY --chown=root:root frontend/ /app/frontend/

USER zakhrafa
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
