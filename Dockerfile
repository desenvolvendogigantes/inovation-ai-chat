# Estágio 1: Build do widget React
FROM node:18-alpine as widget-builder

WORKDIR /app/widget
COPY widget/package.json widget/package-lock.json* ./
RUN npm install
COPY widget/ .
RUN npm run build

# Estágio 2: Backend Python
FROM python:3.11-slim

WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements do backend
COPY backend/requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código do backend
COPY backend/ .

# Copiar widget buildado para servir estáticos
COPY --from=widget-builder /app/widget/dist /app/static/widget

# Criar usuário não-root (segurança)
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

# Comando de inicialização
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
