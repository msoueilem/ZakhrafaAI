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

# --proxy-headers : le schéma (X-Forwarded-Proto) posé par nginx est pris en
# compte, sinon les URL absolues générées par l'application (redirections)
# partent en http://. Pairs de confiance restreints aux plages privées :
# nginx, sur l'hôte, joint le conteneur via le pont Docker (passerelle en
# 172.16.0.0/12) ; 127.0.0.1 couvre le HEALTHCHECK. uvicorn accepte des réseaux
# CIDR dans --forwarded-allow-ips depuis au moins 0.32 (plancher de
# requirements.txt ; vérifié dans 0.32.0 et 0.54.0). Le port n'est de toute
# façon publié que sur 127.0.0.1 (docker-compose.yml). La limite de rendus IA
# par adresse s'appuie sur X-Real-IP, que nginx écrase avec $remote_addr
# (cf. app/net.py, client_ip()).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"]
