import asyncio
import random
from typing import List
from .schemas import LLMAgent, LLMResponse

class MockLLM:
    def __init__(self):
        self.responses = [
            "Essa é uma perspectiva interessante. O que você acha sobre {topic}?",
            "Concordo em partes, mas vejo também que {topic} pode ter outro ângulo.",
            "Baseado no que foi discutido, acredito que {topic} merece mais análise.",
            "Interessante seu ponto! E se considerarmos que {topic} pode ser diferente?",
            "Vamos explorar mais esse aspecto de {topic}. Há várias camadas a considerar.",
            "Excelente observação! Isso me faz pensar que {topic} é mais complexo.",
            "Não havia considerado esse aspecto de {topic}. Pode elaborar mais?",
            "Isso me lembra que {topic} pode ser abordado de forma diferente.",
            "Fascinante! Isso mostra como {topic} é multifacetado.",
            "Bom ponto! Isso se conecta com {topic} de maneira inesperada."
        ]
        
        self.questions = [
            "Qual sua opinião sobre isso?",
            "Como você vê essa questão?",
            "O que mais podemos considerar?",
            "Há outros aspectos relevantes?",
            "Como isso se relaciona com o tema principal?"
        ]
    
    async def generate_response(self, agent: LLMAgent, message: str, conversation_history: List[dict]) -> LLMResponse:
        
        await asyncio.sleep(random.uniform(1.0, 3.0))
        
        topic = self._extract_topic(message) or "este tópico"
        
        if random.random() < 0.7:  
            template = random.choice(self.responses)
            content = template.format(topic=topic)
        else:
            content = f"{random.choice(self.responses).format(topic=topic)} {random.choice(self.questions)}"
        
        content = f"{agent.name}: {content}"
        
        return LLMResponse(
            content=content,
            tokens_used=random.randint(50, 150),
            success=True,
            is_mock=True
        )
    
    def _extract_topic(self, message: str) -> str:
        keywords = [
            "inteligência artificial", "IA", "tecnologia", "educação", 
            "saúde", "negócios", "futuro", "inovação", "sociedade",
            "machine learning", "deep learning", "chatbots", "automação"
        ]
        
        message_lower = message.lower()
        for keyword in keywords:
            if keyword in message_lower:
                return keyword
        
        return ""

mock_llm = MockLLM()
