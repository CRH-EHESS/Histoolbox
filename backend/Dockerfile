FROM python:3.11-slim

WORKDIR /app

# uv pour la gestion des dépendances
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dépendances d'abord (cache Docker optimal). L'environnement /app/.venv est
# complet dès le build, sans le groupe dev : rien n'est installé au démarrage.
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Code source
COPY app/ ./app/
# Point d'entrée du worker RQ (utilisé par le service rq_worker dans docker-compose)
COPY run_worker.py ./

# Répertoires de données (montés en volume en prod)
RUN mkdir -p data/uploads data/outputs

EXPOSE 8001

# Commande par défaut : API, lancée depuis le venv construit au build. Pas de
# `uv run` : il resynchroniserait l'environnement au démarrage, groupe dev
# compris, en téléchargeant depuis PyPI.
# Le service rq_worker surcharge cette commande via docker-compose :
#   command: ["/app/.venv/bin/python", "run_worker.py"]
# --proxy-headers : client réel lu dans X-Forwarded-For, pour les seules IP
# listées dans FORWARDED_ALLOW_IPS (sous-réseau Compose, voir docker-compose.yml).
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers"]
