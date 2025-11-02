import asyncio
import json
import logging
import uuid
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import os
import httpx

from openai import AsyncOpenAI
import google.generativeai as genai
import anthropic

from ..config.settings import settings
from ..redis_client import redis_client
from ..config.llm_config import llm_config

# Configuração de logging
logger = logging.getLogger(__name__)

class LLMOrchestrator:
    
    def __init__(self, storage):
        self.storage = storage
        self.active_debates: Dict[str, Any] = {}
        self.agents: Dict[str, Any] = self._load_agents_from_config()
        self._setup_providers()
        
        # Estatísticas para observabilidade
        self.stats = {
            "total_debates": 0,
            "completed_debates": 0,
            "total_tokens": 0,
            "errors_by_provider": {},
            "avg_latency_by_provider": {}
        }

    def _setup_providers(self):
        self.providers = {}
        
        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self.providers["openai"] = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            logger.info("✅ OpenAI provider configurado")
        
        # Google Gemini
        if os.getenv("GEMINI_API_KEY"):
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            self.providers["gemini"] = genai
            logger.info("✅ Google Gemini provider configurado")
        
        # Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            self.providers["anthropic"] = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            logger.info("✅ Anthropic provider configurado")
        
        # Ollama
        if os.getenv("OLLAMA_BASE_URL"):
            self.providers["ollama"] = os.getenv("OLLAMA_BASE_URL")
            logger.info("✅ Ollama provider configurado")

    def _load_agents_from_config(self) -> Dict[str, Any]:
        agents = {}
        available_agents = llm_config.get_available_agents()  # ✅ CORREÇÃO: usar get_available_agents()
        
        for agent_config in available_agents:
            try:
                agent_id = agent_config['id']
                agents[agent_id] = {
                    "id": agent_id,
                    "name": agent_config['name'],
                    "provider": agent_config['provider'],
                    "model": agent_config['model'],
                    "temperature": agent_config.get('temperature', 0.7),
                    "max_tokens": agent_config.get('max_tokens', 500),
                    "system_prompt": agent_config.get('system_prompt', 'You are a helpful AI assistant.'),
                    "api_key": agent_config.get('api_key', '')
                }
                logger.info(f"✅ Agente carregado: {agent_config['name']} ({agent_config['provider']})")
            except Exception as e:
                logger.error(f"❌ Erro ao carregar agente {agent_config.get('id', 'unknown')}: {e}")
        
        # ✅ CORREÇÃO: Garantir que os agentes mock estão carregados
        if not agents:
            logger.warning("⚠️ Nenhum agente carregado do config, usando agentes mock padrão")
            agents['mock-a'] = {
                "id": "mock-a",
                "name": "Mock Agent A",
                "provider": "mock",
                "model": "mock",
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": "You are Mock Agent A. Always respond with creative ideas."
            }
            agents['mock-b'] = {
                "id": "mock-b", 
                "name": "Mock Agent B",
                "provider": "mock",
                "model": "mock",
                "temperature": 0.7,
                "max_tokens": 500,
                "system_prompt": "You are Mock Agent B. Always respond with analytical insights."
            }
        
        logger.info(f"📊 Total de agentes carregados: {len(agents)}")
        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """✅ MÉTODO ADICIONADO: Busca agente pelo ID"""
        agent = self.agents.get(agent_id)
        if not agent:
            logger.error(f"❌ Agente não encontrado: {agent_id}")
            logger.error(f"📋 Agentes disponíveis: {list(self.agents.keys())}")
        return agent

    async def call_llm(self, agent: Dict[str, Any], prompt: str, context: List[str] = None) -> Dict[str, Any]:
        start_time = datetime.now()
        
        try:
            # ✅ TIMEOUT por turno (15s)
            if agent["provider"] == "mock":
                response = await self._call_mock_llm(agent, prompt)
            else:
                response = await asyncio.wait_for(
                    self._call_real_llm(agent, prompt, context),
                    timeout=15  # 15s 
                )
            
            latency = (datetime.now() - start_time).total_seconds()
            
            # Atualizar estatísticas
            self._update_stats(agent["provider"], True, latency, response.get("tokens_used", 0))
            
            return {
                "content": response["content"],
                "tokens_used": response.get("tokens_used", 0),
                "latency": latency,
                "success": True,
                "provider": agent["provider"]
            }
            
        except asyncio.TimeoutError:
            logger.error(f"⏰ Timeout chamando {agent['name']} ({agent['provider']})")
            self._update_stats(agent["provider"], False, 15, 0)
            return {
                "content": f"Timeout: {agent['name']} não respondeu em 15 segundos",
                "tokens_used": 0,
                "latency": 15,
                "success": False,
                "provider": agent["provider"],
                "error": "timeout"
            }
        except Exception as e:
            logger.error(f"❌ Erro chamando {agent['name']}: {e}")
            latency = (datetime.now() - start_time).total_seconds()
            self._update_stats(agent["provider"], False, latency, 0)
            return {
                "content": f"Erro: {str(e)}",
                "tokens_used": 0,
                "latency": latency,
                "success": False,
                "provider": agent["provider"],
                "error": str(e)
            }

    async def _call_mock_llm(self, agent: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        await asyncio.sleep(1)
        
        responses = [
            f"Como {agent['name']}, analisando '{prompt}', vejo oportunidades interessantes.",
            f"{agent['name']} aqui: '{prompt}' levanta questões importantes a considerar.",
            f"Perspectiva do {agent['name']}: {prompt} apresenta desafios e oportunidades.",
            f"Como {agent['name']}, acredito que {prompt} merece análise aprofundada.",
            f"{agent['name']} analisando: {prompt} sugere múltiplas abordagens."
        ]
        
        content = responses[len(prompt) % len(responses)]
        
        return {
            "content": content,
            "tokens_used": len(content.split())
        }

    async def _call_real_llm(self, agent: Dict[str, Any], prompt: str, context: List[str] = None) -> Dict[str, Any]:
        provider = agent["provider"]
        
        if provider == "openai" and "openai" in self.providers:
            return await self._call_openai(agent, prompt, context)
        elif provider == "gemini" and "gemini" in self.providers:
            return await self._call_gemini(agent, prompt, context)
        elif provider == "anthropic" and "anthropic" in self.providers:
            return await self._call_anthropic(agent, prompt, context)
        elif provider == "ollama" and "ollama" in self.providers:
            return await self._call_ollama(agent, prompt, context)
        else:
            return await self._call_mock_llm(agent, prompt)

    async def _call_openai(self, agent: Dict[str, Any], prompt: str, context: List[str] = None) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": agent["system_prompt"]}
        ]
        
        if context:
            for msg in context[-4:]: 
                messages.append({"role": "user", "content": msg})
        
        messages.append({"role": "user", "content": prompt})
        
        response = await self.providers["openai"].chat.completions.create(
            model=agent["model"],
            messages=messages,
            temperature=agent["temperature"],
            max_tokens=agent["max_tokens"]
        )
        
        return {
            "content": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens if response.usage else 0
        }

    async def _call_gemini(self, agent: Dict[str, Any], prompt: str, context: List[str] = None) -> Dict[str, Any]:
        model = genai.GenerativeModel(agent["model"])
        
        # Construir contexto
        full_prompt = f"System: {agent['system_prompt']}\n\n"
        if context:
            for msg in context[-4:]:
                full_prompt += f"Previous: {msg}\n"
        full_prompt += f"User: {prompt}"
        
        response = model.generate_content(full_prompt)
        
        return {
            "content": response.text,
            "tokens_used": 0
        }

    async def _call_anthropic(self, agent: Dict[str, Any], prompt: str, context: List[str] = None) -> Dict[str, Any]:
        message = await self.providers["anthropic"].messages.create(
            model=agent["model"],
            max_tokens=agent["max_tokens"],
            temperature=agent["temperature"],
            system=agent["system_prompt"],
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {
            "content": message.content[0].text,
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens
        }

    async def _call_ollama(self, agent: Dict[str, Any], prompt: str, context: List[str] = None) -> Dict[str, Any]:
        url = f"{self.providers['ollama']}/api/generate"
        
        data = {
            "model": agent["model"],
            "prompt": prompt,
            "system": agent["system_prompt"],
            "options": {
                "temperature": agent["temperature"],
                "num_predict": agent["max_tokens"]
            },
            "stream": False
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, timeout=30)
            result = response.json()
            
            return {
                "content": result.get("response", ""),
                "tokens_used": result.get("eval_count", 0)
            }

    def _update_stats(self, provider: str, success: bool, latency: float, tokens: int):
        if success:
            self.stats["total_tokens"] += tokens
            
            # Atualizar latência média
            if provider not in self.stats["avg_latency_by_provider"]:
                self.stats["avg_latency_by_provider"][provider] = []
            self.stats["avg_latency_by_provider"][provider].append(latency)
        else:
            if provider not in self.stats["errors_by_provider"]:
                self.stats["errors_by_provider"][provider] = 0
            self.stats["errors_by_provider"][provider] += 1

    async def start_debate(self, room_id: str, config: Dict[str, Any]) -> str:
        debate_id = str(uuid.uuid4())
        
        # ✅ CORREÇÃO: Usar o método get_agent e logs detalhados
        agent_a_id = config["agent_a_id"]
        agent_b_id = config["agent_b_id"]
        
        logger.info(f"🔍 Buscando agente A: {agent_a_id}")
        logger.info(f"🔍 Buscando agente B: {agent_b_id}")
        logger.info(f"📋 Agentes disponíveis: {list(self.agents.keys())}")
        
        agent_a = self.get_agent(agent_a_id)
        agent_b = self.get_agent(agent_b_id)
        
        if not agent_a:
            raise ValueError(f"Agente A não encontrado: {agent_a_id}")
        if not agent_b:
            raise ValueError(f"Agente B não encontrado: {agent_b_id}")
        
        debate_settings = llm_config.get_debate_settings()
        max_rounds = config.get("max_rounds", debate_settings.get('max_rounds', 6))
        max_duration = config.get("max_duration", debate_settings.get('max_duration', 90))
        
        self.active_debates[debate_id] = {
            "room_id": room_id,
            "agent_a": agent_a,
            "agent_b": agent_b,
            "topic": config["topic"],
            "current_round": 0,
            "max_rounds": max_rounds,
            "started_at": datetime.now(),
            "max_duration": max_duration,
            "is_active": True,
            "context": [],
            "messages": []
        }
        
        self.stats["total_debates"] += 1
        
        start_message = {
            "type": "system",
            "room": room_id,
            "user": {"id": "system", "name": "Sistema"},
            "content": f"🤖 Debate LLM iniciado: {agent_a['name']} vs {agent_b['name']}",
            "ts": int(datetime.now().timestamp() * 1000),
            "client_id": None,
            "meta": {
                "action": "llm_debate_started",
                "debate_id": debate_id,
                "topic": config["topic"],
                "agent_a": config["agent_a_id"],
                "agent_b": config["agent_b_id"],
                "max_rounds": max_rounds,
                "max_duration": max_duration * 1000  # ms
            }
        }
        
        await self.storage.publish_message(room_id, start_message)
        await self.storage.add_to_history(room_id, start_message)
        
        # Iniciar debate em background
        asyncio.create_task(self._run_debate(debate_id))
        
        logger.info(f"🎬 Debate iniciado: {debate_id} em {room_id}")
        return debate_id

    async def stop_debate(self, debate_id: str, reason: str = "manual"):
        if debate_id in self.active_debates:
            self.active_debates[debate_id]["is_active"] = False
            
            debate = self.active_debates[debate_id]
            
            end_message = {
                "type": "system", 
                "room": debate["room_id"],
                "user": {"id": "system", "name": "Sistema"},
                "content": f"⏹️ Debate LLM finalizado ({reason})",
                "ts": int(datetime.now().timestamp() * 1000),
                "client_id": None,
                "meta": {
                    "action": "llm_debate_stopped",
                    "debate_id": debate_id,
                    "total_rounds": debate['current_round'],
                    "duration": (datetime.now() - debate['started_at']).seconds,
                    "reason": reason
                }
            }
            
            await self.storage.publish_message(debate["room_id"], end_message)
            await self.storage.add_to_history(debate["room_id"], end_message)
            
            self.stats["completed_debates"] += 1
            del self.active_debates[debate_id]
            
            logger.info(f"⏹️ Debate finalizado: {debate_id} - {reason}")

    async def _run_debate(self, debate_id: str):
        debate = self.active_debates[debate_id]
        room_id = debate["room_id"]
        
        current_prompt = debate["topic"]
        turn_timeout = 15  # ✅ 15s
        
        while (debate["is_active"] and 
               debate["current_round"] < debate["max_rounds"] and
               (datetime.now() - debate["started_at"]).seconds < debate["max_duration"]):
            
            is_agent_a_turn = debate["current_round"] % 2 == 0
            current_agent = debate["agent_a"] if is_agent_a_turn else debate["agent_b"]
            
            try:
                # Chamar LLM com timeout
                llm_response = await self.call_llm(current_agent, current_prompt, debate["context"])
                
                if llm_response["success"]:
                    agent_message = {
                        "type": "message",
                        "room": room_id,
                        "user": {
                            "id": f"agent:{current_agent['provider']}:{current_agent['model']}",  # EXATO PDF
                            "name": current_agent["name"],
                            "avatar": "🤖"
                        },
                        "content": llm_response["content"],
                        "ts": int(datetime.now().timestamp() * 1000),
                        "client_id": None,
                        "meta": {
                            "agent": True,
                            "provider": current_agent["provider"],
                            "model": current_agent["model"],
                            "debate_id": debate_id,
                            "current_round": debate["current_round"] + 1,
                            "total_rounds": debate["max_rounds"],
                            "tokens_used": llm_response["tokens_used"],
                            "latency": llm_response["latency"]
                        }
                    }
                    
                    await self.storage.publish_message(room_id, agent_message)
                    await self.storage.add_to_history(room_id, agent_message)
                    
                    debate["context"].append(llm_response["content"])
                    debate["messages"].append(agent_message)
                    current_prompt = llm_response["content"]
                    debate["current_round"] += 1
                    
                    round_message = {
                        "type": "system",
                        "room": room_id,
                        "user": {"id": "system", "name": "Sistema"},
                        "content": f"🔄 Rodada {debate['current_round']}/{debate['max_rounds']}",
                        "ts": int(datetime.now().timestamp() * 1000),
                        "client_id": None,
                        "meta": {
                            "action": "llm_debate_round",
                            "debate_id": debate_id,
                            "current_round": debate["current_round"],
                            "current_agent": current_agent["id"],
                            "max_rounds": debate["max_rounds"]
                        }
                    }
                    await self.storage.publish_message(room_id, round_message)
                    
                    logger.info(f"🤖 Debate {debate_id} - Rodada {debate['current_round']}/{debate['max_rounds']} - {current_agent['name']}")
                    
                    # Pequena pausa entre turnos
                    await asyncio.sleep(2)
                else:
                    # Erro no LLM - parar debate
                    await self.stop_debate(debate_id, f"llm_error_{current_agent['provider']}")
                    break
                    
            except asyncio.TimeoutError:
                logger.error(f"⏰ Timeout no turno {debate['current_round'] + 1} do debate {debate_id}")
                await self.stop_debate(debate_id, "turn_timeout")
                break
            except Exception as e:
                logger.error(f"❌ Erro no debate {debate_id}: {e}")
                await self.stop_debate(debate_id, "error")
                break
        
        # Finalizar se atingiu limites
        if debate["current_round"] >= debate["max_rounds"]:
            await self.stop_debate(debate_id, "max_rounds")
        elif (datetime.now() - debate["started_at"]).seconds >= debate["max_duration"]:
            await self.stop_debate(debate_id, "max_duration")

    async def get_active_debates(self) -> List[dict]:
        return [
            {
                "debate_id": debate_id,
                "room_id": debate["room_id"],
                "topic": debate["topic"],
                "agent_a": debate["agent_a"]["name"],
                "agent_b": debate["agent_b"]["name"],
                "current_round": debate["current_round"],
                "max_rounds": debate["max_rounds"],
                "is_active": debate["is_active"],
                "started_at": debate["started_at"].isoformat(),
                "duration_seconds": (datetime.now() - debate["started_at"]).seconds
            }
            for debate_id, debate in self.active_debates.items()
        ]

    def get_stats(self) -> Dict[str, Any]:
        avg_latency = {}
        for provider, latencies in self.stats["avg_latency_by_provider"].items():
            avg_latency[provider] = sum(latencies) / len(latencies) if latencies else 0
        
        return {
            **self.stats,
            "avg_latency_by_provider": avg_latency,
            "active_debates_count": len(self.active_debates),
            "available_providers": list(self.providers.keys())
        }
