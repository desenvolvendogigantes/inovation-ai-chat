import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional
from .schemas import User

# Chave secreta para JWT (em produção usar variável de ambiente)
SECRET_KEY = "inovation-ai-chat-secret-key"

def create_guest_token(user: User) -> str:
    """Cria um token JWT para usuário convidado"""
    payload = {
        "user_id": user.id,
        "name": user.name,
        "type": "guest",
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token: str) -> Optional[User]:
    """Verifica e decodifica um token JWT"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return User(id=payload["user_id"], name=payload["name"])
    except jwt.InvalidTokenError:
        return None
