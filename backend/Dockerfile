FROM python:3.11-slim

WORKDIR /app

# uv pour la gestion des dépendances
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Dépendances d'abord (cache Docker optimal)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

# Code source
COPY app/ ./app/

# Répertoires de données (montés en volume en prod)
RUN mkdir -p data/uploads data/outputs

EXPOSE 8001

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
