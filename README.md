# Inovation AI — Chat Widget com LLM↔LLM

Chat em tempo real com WebSocket, Redis Pub/Sub e debate entre LLMs.

## Instalação

Via Docker Compose (Recomendado)

# 1. Clone o repositório
git clone <seu-repositorio>
cd inovation-ai-chat

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env com suas chaves API

# 3. Execute a aplicação
docker compose up --build

# 4. Acesse os serviços:
# - Página Demo: http://localhost:8080
# - Widget Dev: http://localhost:5173
# - API Backend: http://localhost:8000
# - Redis: localhost:6379

Desenvolvimento Local

# Backend
cd backend
pip install -r requirements.txt
venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (outro terminal)
cd widget
npm install
npm run dev

# Redis
docker run -p 6379:6379 redis:7-alpine

## Diagrama de Arquitetura

    Frontend
        A[Widget React]
        B[Página Demo HTML]
    
    Backend
        C[FastAPI WebSocket]
        D[LLM Orchestrator]
    
    Infraestrutura
        E[Redis Pub/Sub]
        F[LLM Providers]
    
    LLM Providers
        G[OpenAI]
        H[Gemini]
        K[Mock]
