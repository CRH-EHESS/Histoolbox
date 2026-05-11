#!/bin/bash

# --- Couleurs pour la lisibilité ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Lancement de Histoolbox...${NC}\n"

# Fonction pour arrêter les processus en arrière-plan à la fermeture du script
cleanup() {
    echo -e "\n${BLUE}🛑 Arrêt des services...${NC}"
    kill $BACKEND_PID $FRONTEND_PID
    exit
}

trap cleanup SIGINT

# 1. Lancement du Backend
echo -e "${GREEN}[Backend]${NC} Synchronisation et démarrage sur le port 8001..."
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!
cd ..

# 2. Lancement du Frontend
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
echo -e "💡 N'oubliez pas de lancer 'chandra_vllm' dans un terminal séparé.\n"

# Maintenir le script en vie pour capturer le SIGINT
wait