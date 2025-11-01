import os
import yaml
from typing import Dict, Any, List
from pathlib import Path
from .settings import settings

class LLMConfig:
    
    def __init__(self):
        self.config_path = Path(__file__).parent / "llm_providers.yaml"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return self._get_default_config()
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        self._expand_env_vars(config)
        return config
    
    def _expand_env_vars(self, config: Dict[str, Any]):
        """Expandir variáveis de ambiente nos valores"""
        if 'agents' in config:
            for agent_id, agent_config in config['agents'].items():
                if 'api_key' in agent_config and agent_config['api_key'].startswith('${'):
                    env_var = agent_config['api_key'][2:-1]
                    agent_config['api_key'] = os.getenv(env_var, '')
        
        if 'providers' in config:
            for provider_name, provider_config in config['providers'].items():
                if 'api_key' in provider_config and provider_config['api_key'].startswith('${'):
                    env_var = provider_config['api_key'][2:-1]
                    provider_config['api_key'] = os.getenv(env_var, '')
                
                if 'base_url' in provider_config and provider_config['base_url'].startswith('${'):
                    env_var = provider_config['base_url'][2:-1]
                    default = provider_config['base_url'].split(':-')[-1][:-1] if ':-' in provider_config['base_url'] else ''
                    provider_config['base_url'] = os.getenv(env_var, default)
    
    def _get_default_config(self) -> Dict[str, Any]:
        return {
            'agents': {
                'mock-a': {
                    'id': 'mock-a',
                    'name': 'Mock Agent A',
                    'provider': 'mock',
                    'model': 'mock',
                    'temperature': 0.7,
                    'max_tokens': 500,
                    'system_prompt': 'You are Mock Agent A.',
                    'api_key': ''
                },
                'mock-b': {
                    'id': 'mock-b',
                    'name': 'Mock Agent B',
                    'provider': 'mock',
                    'model': 'mock',
                    'temperature': 0.7,
                    'max_tokens': 500,
                    'system_prompt': 'You are Mock Agent B.',
                    'api_key': ''
                }
            },
            'debate_settings': {
                'max_rounds': 6,
                'max_duration': 90,
                'turn_timeout': 15
            }
        }
    
    def get_agents(self) -> Dict[str, Dict[str, Any]]:
        return self.config.get('agents', {})
    
    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        return self.config.get('agents', {}).get(agent_id, {})
    
    def get_available_agents(self) -> List[Dict[str, Any]]:
        agents = []
        for agent_id, agent_config in self.get_agents().items():
            agents.append({
                'id': agent_config['id'],
                'name': agent_config['name'],
                'provider': agent_config['provider'],
                'model': agent_config['model'],
                'available': self._is_agent_available(agent_config)
            })
        return agents
    
    def _is_agent_available(self, agent_config: Dict[str, Any]) -> bool:
        if agent_config['provider'] == 'mock':
            return True
        
        provider_config = self.config.get('providers', {}).get(agent_config['provider'], {})
        api_key = provider_config.get('api_key', '')
        
        return not provider_config.get('required', False) or bool(api_key)
    
    def get_debate_settings(self) -> Dict[str, Any]:
        return self.config.get('debate_settings', {
            'max_rounds': 6,
            'max_duration': 90,
            'turn_timeout': 15
        })

llm_config = LLMConfig()
