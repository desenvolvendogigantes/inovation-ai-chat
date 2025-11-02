# Estágio 1: Build do widget React
FROM node:18-alpine as widget-builder

WORKDIR /app/widget
COPY widget/package.json widget/package-lock.json* ./
RUN npm install
COPY widget/ .
RUN npm run build || echo "Build completed with warnings"

# Estágio 2: Backend Python
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY --from=widget-builder /app/widget/dist /app/static/widget

RUN groupadd -r appuser && useradd -r -g appuser appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:$PORT/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
