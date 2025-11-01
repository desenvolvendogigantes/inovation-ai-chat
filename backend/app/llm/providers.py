import os
import asyncio
from typing import Dict, Any, Optional
import openai
from openai import AsyncOpenAI
import google.generativeai as genai
from .schemas import LLMAgent, LLMResponse

class LLMProvider:
    def __init__(self):
        self.openai_client = None
        self.gemini_client = None
        self.setup_clients()
    
    def setup_clients(self):
        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Google Gemini
        if os.getenv("GEMINI_API_KEY"):
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    
    async def generate_response(self, agent: LLMAgent, message: str, conversation_history: list) -> LLMResponse:
        """Gera resposta usando o provedor específico do agente"""
        
        if agent.provider == "openai" and self.openai_client:
            return await self._openai_generate(agent, message, conversation_history)
        elif agent.provider == "google" and self.gemini_client:
            return await self._gemini_generate(agent, message, conversation_history)
        else:
            return await self._mock_generate(agent, message, conversation_history)
    
    async def _openai_generate(self, agent: LLMAgent, message: str, conversation_history: list) -> LLMResponse:
        try:
            messages = [
                {"role": "system", "content": agent.system_prompt}
            ]
            
            # Adicionar histórico da conversa
            for msg in conversation_history[-6:]:  # Últimas 6 mensagens para contexto
                role = "assistant" if msg.get("is_agent") else "user"
                messages.append({"role": role, "content": msg.get("content", "")})
            
            messages.append({"role": "user", "content": message})
            
            response = await self.openai_client.chat.completions.create(
                model=agent.model,
                messages=messages,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                success=True
            )
            
        except Exception as e:
            return LLMResponse(
                content=f"Erro ao gerar resposta: {str(e)}",
                tokens_used=0,
                success=False
            )
    
    async def _gemini_generate(self, agent: LLMAgent, message: str, conversation_history: list) -> LLMResponse:
        try:
            # Configurar o modelo Gemini
            model = genai.GenerativeModel(agent.model)
            
            # Construir contexto do histórico
            context = f"System: {agent.system_prompt}\n\n"
            for msg in conversation_history[-6:]:
                speaker = "Assistant" if msg.get("is_agent") else "User"
                context += f"{speaker}: {msg.get('content', '')}\n"
            
            context += f"User: {message}"
            
            response = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: model.generate_content(context)
            )
            
            return LLMResponse(
                content=response.text,
                tokens_used=0,  # Gemini não retorna contagem de tokens facilmente
                success=True
            )
            
        except Exception as e:
            return LLMResponse(
                content=f"Erro ao gerar resposta Gemini: {str(e)}",
                tokens_used=0,
                success=False
            )

llm_provider = LLMProvider()
