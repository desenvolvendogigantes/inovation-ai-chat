from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
import re


class User(BaseModel):
    """User model representing a chat participant."""
    
    id: str
    name: str = Field(..., min_length=1, max_length=50, description="User display name")
    avatar: Optional[str] = Field(None, description="Optional avatar URL")


class ChatMessage(BaseModel):
    """Chat message model with validation for real-time communication."""
    
    type: str = Field(
        ..., 
        pattern="^(message|presence|typing|system|error)$",
        description="Message type: message, presence, typing, system, or error"
    )
    room: str = Field(..., min_length=1, max_length=50, description="Chat room identifier")
    user: User = Field(..., description="User who sent the message")
    content: Optional[str] = Field(None, description="Message content")
    ts: int = Field(..., description="Timestamp in milliseconds")
    client_id: Optional[str] = Field(None, description="Client-generated message ID")
    meta: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    code: Optional[str] = Field(None, description="Error code for type=error messages")

    @validator('content')
    def validate_content_length(cls, value: Optional[str]) -> Optional[str]:  # pylint: disable=no-self-argument
        """
        Validate that message content does not exceed maximum length.
        
        Args:
            value: The message content to validate
            
        Returns:
            The validated content
            
        Raises:
            ValueError: If content exceeds 1000 characters
        """
        if value and len(value) > 1000:
            raise ValueError('Message content too long (max 1000 characters)')
        return value

    @validator('room')
    def validate_room_name(cls, value: str) -> str:  # pylint: disable=no-self-argument
        """
        Validate room name format.
        
        Args:
            value: The room name to validate
            
        Returns:
            The validated room name
            
        Raises:
            ValueError: If room name contains invalid characters
        """
        # Allow alphanumeric, hyphens, and underscores
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise ValueError('Room name can only contain letters, numbers, hyphens, and underscores')
        return value


class LLMAgent(BaseModel):
    """LLM agent configuration model."""
    
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Display name for the agent")
    provider: str = Field(..., description="LLM provider (openai, google, mock)")
    model: str = Field(..., description="Specific model name")
    temperature: float = Field(
        default=0.7, 
        ge=0.0, 
        le=2.0,
        description="Sampling temperature for response generation"
    )
    max_tokens: int = Field(
        default=500,
        ge=1, 
        le=4000,
        description="Maximum tokens in generated response"
    )
    system_prompt: str = Field(
        default="You are a helpful AI assistant.",
        description="System prompt defining agent behavior"
    )


class DebateSession(BaseModel):
    """LLM debate session model."""
    
    id: str = Field(..., description="Unique session identifier")
    room: str = Field(..., description="Chat room where debate occurs")
    agent_a: LLMAgent = Field(..., description="First debate participant")
    agent_b: LLMAgent = Field(..., description="Second debate participant")
    topic: str = Field(..., description="Debate topic")
    max_rounds: int = Field(
        default=6,
        ge=1, 
        le=20,
        description="Maximum number of debate rounds"
    )
    current_round: int = Field(
        default=0,
        ge=0,
        description="Current round number"
    )
    is_active: bool = Field(
        default=False,
        description="Whether the debate session is currently active"
    )
    started_at: Optional[int] = Field(
        None,
        description="Session start timestamp in milliseconds"
    )
    ended_at: Optional[int] = Field(
        None,
        description="Session end timestamp in milliseconds"
    )


class RateLimitConfig(BaseModel):
    """Rate limiting configuration model."""
    
    requests: int = Field(
        default=5,
        ge=1,
        description="Number of allowed requests per time window"
    )
    window: int = Field(
        default=5,
        ge=1,
        description="Time window in seconds"
    )
