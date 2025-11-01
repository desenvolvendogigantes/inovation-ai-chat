from fastapi import WebSocket, WebSocketDisconnect, Query, status
from typing import Dict, List, Optional
import json
import uuid
import asyncio
import time
from .redis_client import redis_client

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user: Dict[str, Any], room_id: str):
        await websocket.accept()
        
        # Inicializar sala se não existir
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        
        # Adicionar conexão
        self.active_connections[room_id][user["id"]] = websocket
        
        # Adicionar à presença no Redis - EXATO ws:rooms:{roomId}:online
        await redis_client.add_user_to_room(room_id, user)
        
        # Enviar histórico ao conectar
        await self._send_room_history(websocket, room_id)
        
        # Broadcast presença atualizada
        await self.broadcast_presence(room_id)
        
        # Mensagem de sistema para entrada
        system_message = {
            "type": "system",
            "room": room_id,
            "user": {"id": "system", "name": "System"},
            "content": f"{user['name']} entrou na sala",
            "ts": int(time.time() * 1000),
            "meta": {}
        }
        await self.broadcast_to_room(room_id, system_message)
        
        return user["id"]
    
    async def disconnect(self, user_id: str, user: Dict[str, Any], room_id: str):
        if room_id in self.active_connections and user_id in self.active_connections[room_id]:
            del self.active_connections[room_id][user_id]
        
        # Remover da presença no Redis
        await redis_client.remove_user_from_room(room_id, user)
        
        # Limpar indicador de digitação
        await redis_client.clear_typing_indicator(room_id, user_id)
        
        # Broadcast presença atualizada
        await self.broadcast_presence(room_id)
        
        # Mensagem de sistema para saída
        system_message = {
            "type": "system",
            "room": room_id,
            "user": {"id": "system", "name": "System"},
            "content": f"{user['name']} saiu da sala",
            "ts": int(time.time() * 1000),
            "meta": {}
        }
        await self.broadcast_to_room(room_id, system_message)
    
    async def handle_websocket_connection(self, websocket: WebSocket, room_id: str, user: Dict[str, Any]):
        user_id = await self.connect(websocket, user, room_id)
        
        try:
            while True:
                data = await websocket.receive_text()
                await self._handle_client_message(user, room_id, data)
                
        except WebSocketDisconnect:
            await self.disconnect(user_id, user, room_id)
        except Exception as e:
            print(f"Erro na conexão WebSocket: {e}")
            await self.disconnect(user_id, user, room_id)
    
    async def _handle_client_message(self, user: Dict[str, Any], room_id: str, data: str):
        try:
            message_data = json.loads(data)
            
            # Validar campos obrigatórios
            if not all(k in message_data for k in ["type", "content"]):
                await self._send_error(room_id, user["id"], "Invalid message format")
                return
            
            message_type = message_data["type"]
            content = message_data.get("content", "")
            client_id = message_data.get("client_id")
            
            # Rate limiting
            if not await redis_client.check_rate_limit(room_id, user["id"]):
                await self._send_error(room_id, user["id"], "rate_limited")
                return
            
            if message_type == "message":
                await self._handle_chat_message(user, room_id, content, client_id)
            elif message_type == "typing":
                await self._handle_typing_indicator(user, room_id)
            else:
                await self._send_error(room_id, user["id"], "Unknown message type")
                
        except json.JSONDecodeError:
            await self._send_error(room_id, user["id"], "Invalid JSON")
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
            await self._send_error(room_id, user["id"], "Internal server error")
    
    async def _handle_chat_message(self, user: Dict[str, Any], room_id: str, content: str, client_id: Optional[str] = None):
        # Validar tamanho
        if len(content) > 1000:
            await self._send_error(room_id, user["id"], "Message too long (max 1000 chars)")
            return
        
        # Sanitizar conteúdo - prevenir XSS
        sanitized_content = self._sanitize_content(content)
        
        # Criar mensagem
        message = {
            "type": "message",
            "room": room_id,
            "user": user,
            "content": sanitized_content,
            "ts": int(time.time() * 1000),
            "client_id": client_id,
            "meta": {}
        }
        
        # Adicionar ao histórico Redis - EXATO ws:rooms:{roomId}:history
        await redis_client.add_message_to_history(room_id, message)
        
        # Publicar via Redis Pub/Sub - EXATO ws:rooms:{roomId}:stream
        await redis_client.publish_to_room(room_id, message)
        
        # Limpar indicador de digitação
        await redis_client.clear_typing_indicator(room_id, user["id"])
    
    async def _handle_typing_indicator(self, user: Dict[str, Any], room_id: str):
        # Definir indicador no Redis - EXATO ws:rooms:{roomId}:typing:{userId}
        await redis_client.set_typing_indicator(room_id, user["id"], user["name"])
        
        # Obter lista de usuários digitando
        typing_users = await redis_client.get_typing_users(room_id)
        
        # Broadcast para a sala
        typing_message = {
            "type": "typing",
            "room": room_id,
            "user": {"id": "system", "name": "System"},
            "content": {"typing_users": typing_users},
            "ts": int(time.time() * 1000),
            "meta": {}
        }
        
        await self.broadcast_to_room(room_id, typing_message)
    
    async def _send_room_history(self, websocket: WebSocket, room_id: str):
        history = await redis_client.get_room_history(room_id)
        for message in history:
            try:
                await websocket.send_text(json.dumps(message))
            except:
                break  # Cliente desconectou
    
    async def broadcast_presence(self, room_id: str):
        online_users = await redis_client.get_online_users(room_id)
        online_count = await redis_client.get_online_count(room_id)
        
        presence_message = {
            "type": "presence",
            "room": room_id,
            "user": {"id": "system", "name": "System"},
            "content": {
                "count": online_count,
                "users": online_users
            },
            "ts": int(time.time() * 1000),
            "meta": {}
        }
        
        await self.broadcast_to_room(room_id, presence_message)
    
    async def broadcast_to_room(self, room_id: str, message: Dict[str, Any]):
        # Enviar para conexões locais
        if room_id in self.active_connections:
            disconnected = []
            for user_id, websocket in self.active_connections[room_id].items():
                try:
                    await websocket.send_text(json.dumps(message))
                except:
                    disconnected.append(user_id)
            
            # Limpar conexões desconectadas
            for user_id in disconnected:
                if room_id in self.active_connections and user_id in self.active_connections[room_id]:
                    del self.active_connections[room_id][user_id]
    
    async def _send_error(self, room_id: str, user_id: str, error_code: str):
        error_messages = {
            "rate_limited": "Rate limit exceeded. Please wait before sending more messages.",
            "Invalid JSON": "Invalid JSON format",
            "Invalid message format": "Missing required fields",
            "Message too long": "Message exceeds maximum length",
            "Unknown message type": "Unsupported message type",
            "Internal server error": "Internal server error"
        }
        
        error_message = {
            "type": "error",
            "room": room_id,
            "user": {"id": "system", "name": "System"},
            "content": error_messages.get(error_code, "Unknown error"),
            "ts": int(time.time() * 1000),
            "code": error_code,
            "meta": {}
        }
        
        # Enviar apenas para o usuário específico
        if room_id in self.active_connections and user_id in self.active_connections[room_id]:
            try:
                await self.active_connections[room_id][user_id].send_text(json.dumps(error_message))
            except:
                pass  # Cliente já desconectou
    
    def _sanitize_content(self, content: str) -> str:
        if not content:
            return content
        
        # Sanitização básica - substituir caracteres perigosos
        sanitized = (content
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&#x27;')
                    .replace('/', '&#x2F;'))
        
        return sanitized
    
    async def get_room_stats(self, room_id: str) -> Dict[str, Any]:
        online_count = await redis_client.get_online_count(room_id) if redis_client.connected else 0
        local_count = len(self.active_connections.get(room_id, {}))
        
        return {
            "room_id": room_id,
            "online_users_redis": online_count,
            "local_connections": local_count,
            "connected": redis_client.connected
        }

# Instância global do gerenciador de conexões
connection_manager = ConnectionManager()
