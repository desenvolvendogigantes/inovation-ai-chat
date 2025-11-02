import json
import time
import os
from typing import List, Dict, Any, Optional
import redis.asyncio as redis

def get_redis_url():
    return os.getenv("REDIS_URL", "redis://localhost:6379")

def get_redis_timeout():
    return int(os.getenv("REDIS_TIMEOUT", "5"))

class RedisClient:
    
    def __init__(self):
        self.client = None
        self.connected = False
    
    async def connect(self):
        try:
            redis_url = get_redis_url()
            timeout = get_redis_timeout()
            
            self.client = redis.from_url(
                redis_url, 
                decode_responses=True,
                socket_connect_timeout=timeout,
                socket_timeout=timeout,
                retry_on_timeout=True,
                max_connections=10
            )
            
            await self.client.ping()
            self.connected = True
            print(f"✅ Conectado ao Redis: {redis_url}")
            
        except Exception as e:
            print(f"❌ Redis não disponível: {e}")
            self.connected = False
    
    async def close(self):
        """Fecha conexão Redis"""
        if self.client and self.connected:
            try:
                await self.client.close()
                self.connected = False
                print("✅ Conexão Redis fechada")
            except Exception as e:
                print(f"❌ Erro ao fechar Redis: {e}")
    
    async def publish_to_room(self, room_id: str, message: Dict[str, Any]):
        if not self.connected:
            return
        
        try:
            channel = f"ws:rooms:{room_id}:stream"
            await self.client.publish(channel, json.dumps(message))
        except Exception as e:
            print(f"❌ Erro no publish: {e}")
    
    async def subscribe_to_room(self, room_id: str):
        if not self.connected:
            return None
        
        try:
            channel = f"ws:rooms:{room_id}:stream"
            pubsub = self.client.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            print(f"❌ Erro no subscribe: {e}")
            return None
    
    async def add_message_to_history(self, room_id: str, message: Dict[str, Any]):
        if not self.connected:
            return
        
        try:
            key = f"ws:rooms:{room_id}:history"
            await self.client.lpush(key, json.dumps(message))
            await self.client.ltrim(key, 0, 49)
            await self.client.expire(key, 86400)
        except Exception as e:
            print(f"❌ Erro ao adicionar histórico: {e}")
    
    async def get_room_history(self, room_id: str) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        try:
            key = f"ws:rooms:{room_id}:history"
            messages = await self.client.lrange(key, 0, 49)
            return [json.loads(msg) for msg in reversed(messages)]
        except Exception as e:
            print(f"❌ Erro ao obter histórico: {e}")
            return []
    
    async def add_user_to_room(self, room_id: str, user_data: Dict[str, Any]):
        if not self.connected:
            return
        
        try:
            key = f"ws:rooms:{room_id}:online"
            user_json = json.dumps(user_data)
            await self.client.sadd(key, user_json)
            await self.client.expire(key, 3600)
        except Exception as e:
            print(f"❌ Erro ao adicionar usuário: {e}")
    
    async def remove_user_from_room(self, room_id: str, user_data: Dict[str, Any]):
        if not self.connected:
            return
        
        try:
            key = f"ws:rooms:{room_id}:online"
            user_json = json.dumps(user_data)
            await self.client.srem(key, user_json)
        except Exception as e:
            print(f"❌ Erro ao remover usuário: {e}")
    
    async def get_online_users(self, room_id: str) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        try:
            key = f"ws:rooms:{room_id}:online"
            members = await self.client.smembers(key)
            return [json.loads(member) for member in members]
        except Exception as e:
            print(f"❌ Erro ao obter usuários online: {e}")
            return []
    
    async def get_online_count(self, room_id: str) -> int:
        if not self.connected:
            return 0
        
        try:
            key = f"ws:rooms:{room_id}:online"
            return await self.client.scard(key)
        except Exception as e:
            print(f"❌ Erro ao obter contagem online: {e}")
            return 0
    
    async def set_typing_indicator(self, room_id: str, user_id: str, user_name: str):
        if not self.connected:
            return
        
        try:
            key = f"ws:rooms:{room_id}:typing:{user_id}"
            await self.client.setex(key, 5, user_name)
        except Exception as e:
            print(f"❌ Erro ao definir typing: {e}")
    
    async def get_typing_users(self, room_id: str) -> List[Dict[str, str]]:
        if not self.connected:
            return []
        
        try:
            pattern = f"ws:rooms:{room_id}:typing:*"
            keys = await self.client.keys(pattern)
            
            typing_users = []
            for key in keys:
                user_name = await self.client.get(key)
                if user_name:
                    user_id = key.split(':')[-1]
                    typing_users.append({
                        "id": user_id,
                        "name": user_name
                    })
            
            return typing_users
        except Exception as e:
            print(f"❌ Erro ao obter usuários digitando: {e}")
            return []
    
    async def clear_typing_indicator(self, room_id: str, user_id: str):
        if not self.connected:
            return
        
        try:
            key = f"ws:rooms:{room_id}:typing:{user_id}"
            await self.client.delete(key)
        except Exception as e:
            print(f"❌ Erro ao limpar typing: {e}")
    
    async def check_rate_limit(self, room_id: str, user_id: str) -> bool:
        if not self.connected:
            return True
        
        try:
            key = f"ratelimit:{room_id}:{user_id}"
            now = time.time()
            
            max_requests = 5
            window_seconds = 5
            
            bucket_data = await self.client.get(key)
            if bucket_data:
                last_update, tokens = map(float, bucket_data.split(':'))
            else:
                last_update, tokens = now, max_requests
            
            time_passed = now - last_update
            tokens_to_add = time_passed / window_seconds * max_requests
            tokens = min(max_requests, tokens + tokens_to_add)
            
            if tokens >= 1:
                tokens -= 1
                await self.client.setex(
                    key, 
                    window_seconds * 2,
                    f"{now}:{tokens}"
                )
                return True
            else:
                return False
        except Exception as e:
            print(f"❌ Erro no rate limit: {e}")
            return True
    
    async def get_rate_limit_info(self, room_id: str, user_id: str) -> Dict[str, Any]:
        if not self.connected:
            return {"remaining": 5, "reset_in": 0}
        
        try:
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
        except Exception as e:
            print(f"❌ Erro ao obter info rate limit: {e}")
            return {"remaining": 5, "reset_in": 0}
    
    async def cleanup_expired_typing_indicators(self, room_id: str):
        if not self.connected:
            return
        
        try:
            pattern = f"ws:rooms:{room_id}:typing:*"
            keys = await self.client.keys(pattern)
            
            for key in keys:
                ttl = await self.client.ttl(key)
                if ttl < 0:
                    await self.client.delete(key)
        except Exception as e:
            print(f"❌ Erro ao limpar typing expirado: {e}")

# Instância global
redis_client = RedisClient()
