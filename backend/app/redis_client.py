import json
import time
from typing import List, Dict, Any, Optional
import redis.asyncio as redis
from .config.settings import settings

class RedisClient:
    
    def __init__(self):
        self.client = None
        self.connected = False
    
    async def connect(self):
        try:
            self.client = redis.from_url(settings.REDIS_URL, decode_responses=True)
            await self.client.ping()
            self.connected = True
            print("✅ Conectado ao Redis")
        except Exception as e:
            print(f"❌ Redis não disponível: {e}")
            self.connected = False
    
    async def close(self):
        if self.client and self.connected:
            await self.client.close()
    
    async def publish_to_room(self, room_id: str, message: Dict[str, Any]):
        if not self.connected:
            return
        
        channel = f"ws:rooms:{room_id}:stream"
        await self.client.publish(channel, json.dumps(message))
    
    async def subscribe_to_room(self, room_id: str):
        if not self.connected:
            return None
        
        channel = f"ws:rooms:{room_id}:stream"
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub
    
    async def add_message_to_history(self, room_id: str, message: Dict[str, Any]):
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:history"
        
        await self.client.lpush(key, json.dumps(message))
        
        await self.client.ltrim(key, 0, 49)
        
        await self.client.expire(key, 86400)
    
    async def get_room_history(self, room_id: str) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        key = f"ws:rooms:{room_id}:history"
        messages = await self.client.lrange(key, 0, 49)
        return [json.loads(msg) for msg in reversed(messages)]
    
    async def add_user_to_room(self, room_id: str, user_data: Dict[str, Any]):
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:online"
        user_json = json.dumps(user_data)
        await self.client.sadd(key, user_json)
        
        await self.client.expire(key, 3600)
    
    async def remove_user_from_room(self, room_id: str, user_data: Dict[str, Any]):
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:online"
        user_json = json.dumps(user_data)
        await self.client.srem(key, user_json)
    
    async def get_online_users(self, room_id: str) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        key = f"ws:rooms:{room_id}:online"
        members = await self.client.smembers(key)
        return [json.loads(member) for member in members]
    
    async def get_online_count(self, room_id: str) -> int:
        if not self.connected:
            return 0
        
        key = f"ws:rooms:{room_id}:online"
        return await self.client.scard(key)
    
    async def set_typing_indicator(self, room_id: str, user_id: str, user_name: str):
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:typing:{user_id}"
        await self.client.setex(key, 5, user_name)
    
    async def get_typing_users(self, room_id: str) -> List[Dict[str, str]]:
        if not self.connected:
            return []
        
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
    
    async def clear_typing_indicator(self, room_id: str, user_id: str):
        if not self.connected:
            return
        
        key = f"ws:rooms:{room_id}:typing:{user_id}"
        await self.client.delete(key)
    
    async def check_rate_limit(self, room_id: str, user_id: str) -> bool:
        if not self.connected:
            return True
        
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
    
    async def get_rate_limit_info(self, room_id: str, user_id: str) -> Dict[str, Any]:
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
    
    async def cleanup_expired_typing_indicators(self, room_id: str):
        if not self.connected:
            return
        
        pattern = f"ws:rooms:{room_id}:typing:*"
        keys = await self.client.keys(pattern)
        
        for key in keys:
            ttl = await self.client.ttl(key)
            if ttl < 0:
                await self.client.delete(key)

redis_client = RedisClient()
