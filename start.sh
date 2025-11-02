#!/bin/bash

# Instalar dependências do backend
cd backend
pip install -r requirements.txt

# Build do widget
cd ../widget
npm install
npm run build

# Voltar para raiz e iniciar aplicação
cd ..
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT