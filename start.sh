#!/bin/bash

# --- Couleurs pour la lisibilité ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

REDIS_HOST="localhost"
REDIS_PORT="6379"
REDIS_CONTAINER="histoolbox-redis"

echo -e "${BLUE}🚀 Lancement de Histoolbox...${NC}\n"

is_redis_reachable() {
    (echo > /dev/tcp/${REDIS_HOST}/${REDIS_PORT}) >/dev/null 2>&1
}

start_redis_if_needed() {
    if is_redis_reachable; then
        echo -e "${GREEN}[Redis]${NC} Déjà disponible sur ${REDIS_HOST}:${REDIS_PORT}"
        return 0
    fi

    echo -e "${GREEN}[Redis]${NC} Redis non détecté sur ${REDIS_HOST}:${REDIS_PORT}, tentative de démarrage Docker..."

    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}[Redis]${NC} Docker n'est pas installé. Lance Redis manuellement puis relance start.sh."
        return 1
    fi

    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}[Redis]${NC} Docker n'est pas démarré. Lance Docker puis relance start.sh."
        return 1
    fi

    if docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        echo -e "${GREEN}[Redis]${NC} Conteneur ${REDIS_CONTAINER} déjà en cours d'exécution"
    elif docker ps -a --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
        docker start "${REDIS_CONTAINER}" >/dev/null
        echo -e "${GREEN}[Redis]${NC} Conteneur ${REDIS_CONTAINER} redémarré"
    else
        docker run -d --name "${REDIS_CONTAINER}" -p ${REDIS_PORT}:6379 redis:7-alpine >/dev/null
        echo -e "${GREEN}[Redis]${NC} Conteneur ${REDIS_CONTAINER} créé et démarré"
    fi

    for _ in {1..15}; do
        if is_redis_reachable; then
            echo -e "${GREEN}[Redis]${NC} Disponible sur ${REDIS_HOST}:${REDIS_PORT}"
            return 0
        fi
        sleep 1
    done

    echo -e "${RED}[Redis]${NC} Échec du démarrage Redis sur ${REDIS_HOST}:${REDIS_PORT}"
    return 1
}

# Fonction pour arrêter les processus en arrière-plan à la fermeture du script
cleanup() {
    echo -e "\n${BLUE}🛑 Arrêt des services...${NC}"
    [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" >/dev/null 2>&1
    [ -n "${WORKER_PID:-}" ] && kill "$WORKER_PID" >/dev/null 2>&1
    [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" >/dev/null 2>&1
    exit
}

trap cleanup SIGINT

# 0. Vérification / démarrage Redis
start_redis_if_needed || exit 1

# 1. Lancement du Backend
echo -e "${GREEN}[Backend]${NC} Synchronisation et démarrage sur le port 8001..."
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!
cd ..

# 2. Lancement du Worker RQ
echo -e "${GREEN}[Worker]${NC} Démarrage du worker RQ..."
cd backend
uv run python run_worker.py &
WORKER_PID=$!
cd ..

# 3. Lancement du Frontend
echo -e "${GREEN}[Frontend]${NC} Installation des dépendances et démarrage..."
cd frontend
# Utilise 'npm install' seulement si node_modules n'existe pas pour gagner du temps
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run dev &
FRONTEND_PID=$!
cd ..

echo -e "\n${BLUE}✨ Services démarrés !${NC}"
echo -e "📖 Frontend : http://localhost:5173"
echo -e "⚙️  Backend  : http://localhost:8001"
echo -e "🧵 Worker RQ : démarré (Redis requis sur localhost:6379)"
echo -e "💡 N'oubliez pas de lancer 'chandra_vllm' dans un terminal séparé.\n"

# Maintenir le script en vie pour capturer le SIGINT
wait