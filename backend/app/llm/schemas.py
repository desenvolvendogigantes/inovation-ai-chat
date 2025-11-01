from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    success: bool = True
    error_message: Optional[str] = None
    is_mock: bool = False

class LLMAgent(BaseModel):
    id: str
    name: str
    provider: str  # "openai", "google", "mock"
    model: str
    temperature: float = 0.7
    max_tokens: int = 500
    system_prompt: str = "You are a helpful AI assistant."

class DebateConfig(BaseModel):
    topic: str
    agent_a: LLMAgent
    agent_b: LLMAgent
    max_rounds: int = 6
    max_duration: int = 90  # seconds

class DebateSession(BaseModel):
    id: str
    room: str
    agent_a: LLMAgent
    agent_b: LLMAgent
    topic: str
    max_rounds: int = 6
    current_round: int = 0
    is_active: bool = False
    started_at: Optional[int] = None
    ended_at: Optional[int] = None
