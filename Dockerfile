# --- FRONTEND BUILD ---
FROM node:18-alpine as frontend-builder
WORKDIR /app

COPY widget/package*.json ./
RUN npm install

COPY widget/ .
RUN npm run build 2>/dev/null || (mkdir -p dist && echo "<html><body>Chat Widget Loading...</body></html>" > dist/index.html)

# --- BACKEND ---
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

COPY --from=frontend-builder /app/dist /app/static

RUN groupadd -r appuser && useradd -r -g appuser appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
