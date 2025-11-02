import asyncio
import json
import logging
import uuid
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

# Importar configurações
from .config.settings import settings
from .redis_client import redis_client
from .config.llm_config import llm_config
from .authentication import verify_token, create_guest_token
from .llm.orchestrator import LLMOrchestrator

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class User(BaseModel):
    id: str
    name: str
    avatar: Optional[str] = None

class WebSocketMessage(BaseModel):
    type: str
    room: str
    user: User
    content: Optional[str] = None
    ts: int
    client_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class LLMAgent(BaseModel):
    id: str
    name: str
    provider: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 500
    system_prompt: str = "You are a helpful AI assistant."
    api_key: Optional[str] = None

class DebateConfig(BaseModel):
    room: str = "general"
    agent_a_id: str
    agent_b_id: str
    topic: str
    max_rounds: int = 6
    max_duration: int = 90

class LoginRequest(BaseModel):
    name: str
    displayName: Optional[str] = None

class StorageManager:
    def __init__(self):
        self.redis = redis_client
    
    async def connect(self):
        await self.redis.connect()
    
    async def publish_message(self, room_id: str, message: dict):
        await self.redis.publish_to_room(room_id, message)
    
    async def add_to_history(self, room_id: str, message: dict):
        await self.redis.add_message_to_history(room_id, message)
    
    async def get_history(self, room_id: str) -> List[dict]:
        return await self.redis.get_room_history(room_id)
    
    async def add_user_to_presence(self, room_id: str, user_id: str, user_data: dict):
        await self.redis.add_user_to_room(room_id, {"id": user_id, **user_data})
    
    async def remove_user_from_presence(self, room_id: str, user_id: str):
        await self.redis.remove_user_from_room(room_id, user_id)
    
    async def get_online_users(self, room_id: str) -> List[dict]:
        return await self.redis.get_online_users(room_id)
    
    async def set_typing_indicator(self, room_id: str, user_id: str, user_name: str):
        await self.redis.set_typing_indicator(room_id, user_id, user_name)
    
    async def get_typing_users(self, room_id: str) -> List[str]:
        return await self.redis.get_typing_users(room_id)
    
    async def check_rate_limit(self, user_id: str, room_id: str) -> bool:
        return await self.redis.check_rate_limit(room_id, user_id)
    
    async def get_rate_limit_info(self, user_id: str, room_id: str) -> Dict[str, Any]:
        return await self.redis.get_rate_limit_info(room_id, user_id)

class ConnectionManager:
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.active_connections: Dict[str, WebSocket] = {}
        self.llm_orchestrator = LLMOrchestrator(storage)
    
    async def connect(self, websocket: WebSocket, user_id: str, user_name: str, room_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        
        await self.storage.add_user_to_presence(room_id, user_id, {"name": user_name})
        
        await self.broadcast_presence(room_id)
    
    async def disconnect(self, user_id: str, room_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        await self.storage.remove_user_from_presence(room_id, user_id)
        
        await self.broadcast_presence(room_id)
    
    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Erro ao enviar mensagem para {user_id}: {e}")
    
    async def broadcast_to_room(self, message: dict, room_id: str):
        await self.storage.publish_message(room_id, message)
    
    async def broadcast_presence(self, room_id: str):
        online_users = await self.storage.get_online_users(room_id)
        online_count = len(online_users)
        
        presence_message = {
            "type": "presence",
            "room": room_id,
            "user": {"id": "system", "name": "System"},
            "content": None,
            "ts": int(datetime.now().timestamp() * 1000),
            "client_id": None,
            "meta": {
                "online_count": online_count,
                "users": online_users
            }
        }
        await self.broadcast_to_room(presence_message, room_id)
    
    async def broadcast_typing(self, room_id: str, user_data: User):
        typing_users = await self.storage.get_typing_users(room_id)
        
        typing_message = {
            "type": "typing",
            "room": room_id,
            "user": user_data.dict(),  # ✅ CORREÇÃO: Converter User para dict
            "content": "started" if typing_users else "stopped",
            "ts": int(datetime.now().timestamp() * 1000),
            "client_id": None,
            "meta": {"users": typing_users}
        }
        await self.broadcast_to_room(typing_message, room_id)

def sanitize_content(content: str) -> str:
    if not content:
        return content
    
    content = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'on\w+=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)
    
    content = (content
              .replace('&', '&amp;')
              .replace('<', '&lt;')
              .replace('>', '&gt;')
              .replace('"', '&quot;')
              .replace("'", '&#x27;'))
    
    return content

# Inicialização
storage_manager = StorageManager()
connection_manager = ConnectionManager(storage_manager)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await storage_manager.connect()
    yield
    # Shutdown
    await redis_client.close()

app = FastAPI(
    title="Inovation AI Chat API",
    description="Chat em tempo real com WebSocket e orquestração LLM - CONFORME PDF",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Inovation AI Chat API", 
        "version": "1.0.0",
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/llm/status")
async def llm_status():
    active_debates = await connection_manager.llm_orchestrator.get_active_debates()
    available_agents = llm_config.get_available_agents()
    
    return {
        "active_debates": active_debates,
        "available_agents": available_agents,
        "total_agents": len(available_agents)
    }

@app.get("/agents")
async def list_agents():
    available_agents = llm_config.get_available_agents()
    
    return {
        "agents": available_agents,
        "total_available": len([a for a in available_agents if a['available']])
    }

@app.post("/debate/start")
async def start_debate(config: DebateConfig):
    try:
        config_dict = {
            "agent_a_id": config.agent_a_id,
            "agent_b_id": config.agent_b_id,
            "topic": config.topic,
            "max_rounds": config.max_rounds,
            "max_duration": config.max_duration
        }
        
        debate_id = await connection_manager.llm_orchestrator.start_debate(config.room, config_dict)
        return {
            "debate_id": debate_id, 
            "status": "started",
            "room": config.room,
            "topic": config.topic
        }
    except Exception as e:
        logger.error(f"Erro ao iniciar debate: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/debate/{debate_id}/stop")
async def stop_debate(debate_id: str):
    await connection_manager.llm_orchestrator.stop_debate(debate_id)
    return {"status": "stopped", "debate_id": debate_id}

@app.post("/auth/login")
async def mock_login(login_data: LoginRequest):
    user_id = str(uuid.uuid4())
    user_name = login_data.displayName or login_data.name
    
    token = create_guest_token(User(id=user_id, name=user_name))
    
    return {
        "user": {
            "id": user_id,
            "name": user_name,
            "avatar": None
        },
        "token": token,
        "type": "guest"
    }

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    room: str = "general",
    user_id: str = "anonymous",
    user_name: str = "Guest",
    token: str = "guest"
):
    
    room = re.sub(r'[^a-zA-Z0-9_-]', '', room)[:50]
    user_id = re.sub(r'[^a-zA-Z0-9_-]', '', user_id)[:50]
    user_name = user_name.strip()[:50]
    
    if token == "guest":
        logger.info(f"👤 Usuário convidado conectando: {user_name}")
    else:
        user_from_token = verify_token(token)
        if not user_from_token:
            await websocket.close(code=1008, reason="Token inválido")
            return
        user_id = user_from_token.id
        user_name = user_from_token.name
    
    user_data = User(id=user_id, name=user_name)
    
    await connection_manager.connect(websocket, user_id, user_name, room)
    
    try:
        history = await storage_manager.get_history(room)
        for message in history[-50:]:
            await connection_manager.send_personal_message(message, user_id)
        
        system_message = {
            "type": "system",
            "room": room,
            "user": {"id": "system", "name": "Sistema"},
            "content": f"✅ {user_name} entrou na sala",
            "ts": int(datetime.now().timestamp() * 1000),
            "client_id": None,
            "meta": {
                "action": "user_joined",
                "user_id": user_id,
                "user_name": user_name
            }
        }
        await connection_manager.broadcast_to_room(system_message, room)
        await storage_manager.add_to_history(room, system_message)
        
        logger.info(f"✅ {user_name} conectou à sala {room} (ID: {user_id})")
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message = WebSocketMessage(**message_data)
                
                if message.content and len(message.content) > 1000:
                    error_msg = {
                        "type": "error",
                        "room": room,
                        "user": {"id": "system", "name": "Sistema"},
                        "content": "Mensagem muito longa (máximo 1000 caracteres)",
                        "ts": int(datetime.now().timestamp() * 1000),
                        "client_id": None,
                        "meta": {"code": "message_too_long"}
                    }
                    await connection_manager.send_personal_message(error_msg, user_id)
                    continue
                
                if message.content:
                    message.content = sanitize_content(message.content)
                
                if message.type == "message":
                    if not await storage_manager.check_rate_limit(user_id, room):
                        rate_info = await storage_manager.get_rate_limit_info(user_id, room)
                        error_msg = {
                            "type": "error",
                            "room": room,
                            "user": {"id": "system", "name": "Sistema"},
                            "content": "Muitas mensagens em pouco tempo. Aguarde alguns segundos.",
                            "ts": int(datetime.now().timestamp() * 1000),
                            "client_id": None,
                            "meta": {
                                "code": "rate_limited",
                                "reset_in": rate_info['reset_in']
                            }
                        }
                        await connection_manager.send_personal_message(error_msg, user_id)
                        continue
                
                if message.type == "message":
                    # ✅ CORREÇÃO: Converter User para dict antes de serializar
                    message_dict = message.dict()
                    message_dict['user'] = message.user.dict()
                    
                    await storage_manager.add_to_history(room, message_dict)
                    await connection_manager.broadcast_to_room(message_dict, room)
                    
                elif message.type == "typing":
                    if message.content == "started":
                        await storage_manager.set_typing_indicator(room, user_id, user_name)
                    await connection_manager.broadcast_typing(room, user_data)
                
                elif message.type == "system" and message.meta:
                    action = message.meta.get("action")
                    
                    if action == "llm_debate_start":
                        try:
                            debate_config = {
                                "agent_a_id": message.meta.get("agent_a"),
                                "agent_b_id": message.meta.get("agent_b"),
                                "topic": message.meta.get("topic", "Debate"),
                                "max_rounds": message.meta.get("max_rounds", 6),
                                "max_duration": message.meta.get("max_duration", 90)
                            }
                            debate_id = await connection_manager.llm_orchestrator.start_debate(room, debate_config)
                            
                            await connection_manager.send_personal_message({
                                "type": "system",
                                "room": room,
                                "user": {"id": "system", "name": "Sistema"},
                                "content": f"🎬 Debate iniciado com ID: {debate_id}",
                                "ts": int(datetime.now().timestamp() * 1000),
                                "client_id": None,
                                "meta": {"action": "llm_debate_confirmed", "debate_id": debate_id}
                            }, user_id)
                            
                        except Exception as e:
                            logger.error(f"Erro ao iniciar debate: {e}")
                            await connection_manager.send_personal_message({
                                "type": "error",
                                "room": room,
                                "user": {"id": "system", "name": "Sistema"},
                                "content": f"Erro ao iniciar debate: {str(e)}",
                                "ts": int(datetime.now().timestamp() * 1000),
                                "client_id": None,
                                "meta": {"code": "debate_start_failed"}
                            }, user_id)
                    
                    elif action == "llm_debate_stop":
                        debate_id = message.meta.get("debate_id")
                        if debate_id:
                            await connection_manager.llm_orchestrator.stop_debate(debate_id)
            
            except ValidationError as e:
                logger.error(f"Erro de validação: {e}")
                error_msg = {
                    "type": "error",
                    "room": room,
                    "user": {"id": "system", "name": "Sistema"},
                    "content": "Payload inválido",
                    "ts": int(datetime.now().timestamp() * 1000),
                    "client_id": None,
                    "meta": {"code": "invalid_payload"}
                }
                await connection_manager.send_personal_message(error_msg, user_id)
            except json.JSONDecodeError:
                error_msg = {
                    "type": "error",
                    "room": room,
                    "user": {"id": "system", "name": "Sistema"},
                    "content": "JSON inválido",
                    "ts": int(datetime.now().timestamp() * 1000),
                    "client_id": None,
                    "meta": {"code": "invalid_json"}
                }
                await connection_manager.send_personal_message(error_msg, user_id)
                
    except WebSocketDisconnect:
        logger.info(f"📤 {user_name} desconectou da sala {room}")
    except Exception as e:
        logger.error(f"❌ Erro inesperado no WebSocket: {e}")
    finally:
        await connection_manager.disconnect(user_id, room)
        
        system_message = {
            "type": "system",
            "room": room,
            "user": {"id": "system", "name": "Sistema"},
            "content": f"❌ {user_name} saiu da sala",
            "ts": int(datetime.now().timestamp() * 1000),
            "client_id": None,
            "meta": {
                "action": "user_left",
                "user_id": user_id,
                "user_name": user_name
            }
        }
        try:
            await connection_manager.broadcast_to_room(system_message, room)
            await storage_manager.add_to_history(room, system_message)
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de saída: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0", 
        port=settings.PORT, 
        reload=settings.ENVIRONMENT == "development"
    )
