import json
import time
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
from .config.settings import settings

class RedisClient:
    """Cliente Redis seguindo EXATAMENTE as estruturas chave do PDF"""
    
    def __init__(self):
        self.client = None
        self.connected = False
    
    async def connect(self):
        """Conectar ao Redis"""
        try:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
            self.connected = True
            print("✅ Conectado ao Redis")
        except Exception as e:
            print(f"❌ Redis não disponível: {e}")
            self.connected = False
    
    async def close(self):
        """Fechar conexão"""
        if self.client and self.connected:
            await self.client.close()
    
    # ===== ESTRUTURAS CHAVE DO PDF - EXATAMENTE COMO ESPECIFICADO =====
    
    # 1. Pub/Sub Channel - EXATO
    async def publish_to_room(self, room_id: str, message: Dict[str, Any]):
        """Publicar mensagem no canal Pub/Sub da sala - ws:rooms:{roomId}:stream"""
        if not self.connected:
            return
        
        channel = f"ws:rooms:{room_id}:stream"
        await self.client.publish(channel, json.dumps(message))
    
    async def subscribe_to_room(self, room_id: str):
        """Assinar canal Pub/Sub da sala - ws:rooms:{roomId}:stream"""
        if not self.connected:
            return None
        
        channel = f"ws:rooms:{room_id}:stream"
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
    
    # 2. Message History (List max=50) - EXATO
    async def add_message_to_history(self, room_id: str, message: Dict[str, Any]):
        """Adicionar mensagem ao histórico - ws:rooms:{roomId}:history (max=50)"""
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:history"
        
        # Adicionar à lista
        await self.client.lpush(key, json.dumps(message))
        
        # Manter apenas as últimas 50 mensagens EXATAMENTE como no PDF
        await self.client.ltrim(key, 0, 49)
        
        # Definir TTL de 24 horas (opcional conforme PDF)
        await self.client.expire(key, 86400)
    
    async def get_room_history(self, room_id: str) -> List[Dict[str, Any]]:
        """Obter histórico da sala (últimas 50 mensagens) - ws:rooms:{roomId}:history"""
        if not self.connected:
            return []
        
        key = f"ws:rooms:{room_id}:history"
        messages = await self.client.lrange(key, 0, 49)  # EXATAMENTE 50 mensagens
        return [json.loads(msg) for msg in reversed(messages)]  # Mais recentes primeiro
    
    # 3. Online Users (Set) - EXATO
    async def add_user_to_room(self, room_id: str, user_data: Dict[str, Any]):
        """Adicionar usuário à lista de online - ws:rooms:{roomId}:online"""
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:online"
        user_json = json.dumps(user_data)
        await self.client.sadd(key, user_json)
        
        # Definir TTL para limpeza automática em caso de falha (ex: 1 hora)
        await self.client.expire(key, 3600)
    
    async def remove_user_from_room(self, room_id: str, user_data: Dict[str, Any]):
        """Remover usuário da lista de online - ws:rooms:{roomId}:online"""
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:online"
        user_json = json.dumps(user_data)
        await self.client.srem(key, user_json)
    
    async def get_online_users(self, room_id: str) -> List[Dict[str, Any]]:
        """Obter lista de usuários online - ws:rooms:{roomId}:online"""
        if not self.connected:
            return []
        
        key = f"ws:rooms:{room_id}:online"
        members = await self.client.smembers(key)
        return [json.loads(member) for member in members]
    
    async def get_online_count(self, room_id: str) -> int:
        """Obter contagem de usuários online - ws:rooms:{roomId}:online"""
        if not self.connected:
            return 0
        
        key = f"ws:rooms:{room_id}:online"
        return await self.client.scard(key)
    
    # 4. Typing Indicators (Key com TTL=5s) - EXATO
    async def set_typing_indicator(self, room_id: str, user_id: str, user_name: str):
        """Definir indicador de digitação - ws:rooms:{roomId}:typing:{userId} (TTL=5s)"""
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:typing:{user_id}"
        await self.client.setex(key, 5, user_name)  # TTL de 5 segundos EXATO
    
    async def get_typing_users(self, room_id: str) -> List[Dict[str, str]]:
        """Obter lista de usuários digitando - ws:rooms:{roomId}:typing:*"""
        if not self.connected:
            return []
        
        pattern = f"ws:rooms:{room_id}:typing:*"
        keys = await self.client.keys(pattern)
        
        typing_users = []
        for key in keys:
            user_name = await self.client.get(key)
            if user_name:
                # Extrair user_id da chave
                user_id = key.split(':')[-1]
                typing_users.append({
                    "id": user_id,
                    "name": user_name
                })
        
        return typing_users
    
    async def clear_typing_indicator(self, room_id: str, user_id: str):
        """Limpar indicador de digitação específico"""
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:typing:{user_id}"
        await self.client.delete(key)
    
    # 5. Rate Limiting (Token Bucket) - EXATO - 5 msgs/5s conforme PDF
    async def check_rate_limit(self, room_id: str, user_id: str) -> bool:
        """Verificar rate limit - ratelimit:{roomId}:{userId} (5 msgs/5s)"""
        if not self.connected:
            return True
        
        key = f"ratelimit:{room_id}:{user_id}"
        now = time.time()
        
        # Configuração do rate limit: 5 mensagens a cada 5 segundos
        max_requests = 5
        window_seconds = 5
        
        # Token Bucket Algorithm conforme PDF
        bucket_data = await self.client.get(key)
        if bucket_data:
            last_update, tokens = map(float, bucket_data.split(':'))
        else:
            last_update, tokens = now, max_requests
        
        # Calcular tokens recuperados
        time_passed = now - last_update
        tokens_to_add = time_passed / window_seconds * max_requests
        tokens = min(max_requests, tokens + tokens_to_add)
        
        # Verificar se pode processar
        if tokens >= 1:
            tokens -= 1
            await self.client.setex(
                key, 
                window_seconds * 2,  # TTL generoso
                f"{now}:{tokens}"
            )
            return True
        else:
            return False
    
    async def get_rate_limit_info(self, room_id: str, user_id: str) -> Dict[str, Any]:
        """Obter informações do rate limit para debug"""
        if not self.connected:
            return {"remaining": 5, "reset_in": 0}
        
        key = f"ratelimit:{room_id}:{user_id}"
        now = time.time()
        
        max_requests = 5
        window_seconds = 5
        
        bucket_data = await self.client.get(key)
        if bucket_data:
            last_update, tokens = map(float, bucket_data.split(':'))
            time_passed = now - last_update
            tokens_to_add = time_passed / window_seconds * max_requests
            current_tokens = min(max_requests, tokens + tokens_to_add)
            
            remaining = int(current_tokens)
            reset_in = max(0, (1 - tokens) * window_seconds - time_passed)
        else:
            remaining = max_requests
            reset_in = 0
        
        return {
            "remaining": remaining,
            "limit": max_requests,
            "reset_in": reset_in,
            "window": window_seconds
        }
    
    # 6. Limpeza de recursos expirados
    async def cleanup_expired_typing_indicators(self, room_id: str):
        """Limpar indicadores de digitação expirados"""
        if not self.connected:
            return
        
        pattern = f"ws:rooms:{room_id}:typing:*"
        keys = await self.client.keys(pattern)
        
        for key in keys:
            ttl = await self.client.ttl(key)
            if ttl < 0:  # Chave expirada
                await self.client.delete(key)

# Instância global do cliente Redis
redis_client = RedisClient()
