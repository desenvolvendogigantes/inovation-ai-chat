import React, { useState } from 'react';
import './LLMDebateControls.css';

interface LLMDebateControlsProps {
  roomId: string;
  onStartDebate: (topic: string, agentA: string, agentB: string) => void;
  onStopDebate: () => void;
  isDebateActive: boolean;
  currentTopic?: string;
}

const LLMDebateControls: React.FC<LLMDebateControlsProps> = ({
  roomId,
  onStartDebate,
  onStopDebate,
  isDebateActive,
  currentTopic
}) => {
  const [topic, setTopic] = useState('');
  const [agentA, setAgentA] = useState('gpt-4');
  const [agentB, setAgentB] = useState('gemini-pro');
  const [maxRounds, setMaxRounds] = useState(6);

  const agents = [
    { id: 'gpt-4', name: 'GPT-4', provider: 'OpenAI', description: 'Modelo avançado da OpenAI' },
    { id: 'gpt-3.5', name: 'GPT-3.5 Turbo', provider: 'OpenAI', description: 'Modelo rápido e eficiente' },
    { id: 'gemini-pro', name: 'Gemini Pro', provider: 'Google', description: 'Modelo multimodal do Google' },
    { id: 'claude-2', name: 'Claude 2', provider: 'Anthropic', description: 'Modelo focado em segurança' },
    { id: 'llama-2', name: 'Llama 2', provider: 'Meta', description: 'Modelo open-source' },
    { id: 'mock-agent', name: 'Agente Mock', provider: 'Mock', description: 'Para testes sem API keys' }
  ];

  const handleStartDebate = () => {
    if (topic.trim() && agentA && agentB && agentA !== agentB) {
      onStartDebate(topic.trim(), agentA, agentB);
      setTopic('');
    }
  };

  const getAgentInfo = (agentId: string) => {
    return agents.find(a => a.id === agentId) || agents[0];
  };

  return (
    <div className="llm-debate-controls">
      <div className="debate-header">
        <h4>🤖 Debate LLM ↔ LLM</h4>
        <p>Inicie um debate entre dois agentes de IA</p>
      </div>
      
      {!isDebateActive ? (
        <div className="debate-config">
          <div className="form-group">
            <label htmlFor="debate-topic">Tópico do Debate:</label>
            <textarea
              id="debate-topic"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Ex: Vantagens e desvantagens da inteligência artificial na educação..."
              rows={3}
              maxLength={500}
            />
            <div className="char-count">{topic.length}/500</div>
          </div>

          <div className="agents-selection">
            <div className="form-group">
              <label htmlFor="agent-a">Agente A:</label>
              <select 
                id="agent-a"
                value={agentA} 
                onChange={(e) => setAgentA(e.target.value)}
              >
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} ({agent.provider})
                  </option>
                ))}
              </select>
              <div className="agent-description">
                {getAgentInfo(agentA).description}
              </div>
            </div>

            <div className="vs-separator">
              <span>VS</span>
            </div>

            <div className="form-group">
              <label htmlFor="agent-b">Agente B:</label>
              <select 
                id="agent-b"
                value={agentB} 
                onChange={(e) => setAgentB(e.target.value)}
              >
                {agents.map(agent => (
                  <option key={agent.id} value={agent.id}>
                    {agent.name} ({agent.provider})
                  </option>
                ))}
              </select>
              <div className="agent-description">
                {getAgentInfo(agentB).description}
              </div>
            </div>
          </div>

          <div className="debate-settings">
            <div className="form-group">
              <label htmlFor="max-rounds">Rodadas Máximas:</label>
              <input
                id="max-rounds"
                type="number"
                min="2"
                max="20"
                value={maxRounds}
                onChange={(e) => setMaxRounds(parseInt(e.target.value))}
              />
            </div>
          </div>

          <button 
            onClick={handleStartDebate}
            disabled={!topic.trim() || !agentA || !agentB || agentA === agentB}
            className="start-debate-button"
          >
            🚀 Iniciar Debate
            <span>Agentes: {getAgentInfo(agentA).name} vs {getAgentInfo(agentB).name}</span>
          </button>

          {agentA === agentB && (
            <div className="warning-message">
              ⚠️ Selecione agentes diferentes para um debate interessante
            </div>
          )}
        </div>
      ) : (
        <div className="active-debate">
          <div className="debate-status">
            <div className="status-header">
              <span className="status-indicator">🔴 Debate em Andamento</span>
              <button onClick={onStopDebate} className="stop-debate-button">
                ⏹️ Parar Debate
              </button>
            </div>
            <div className="debate-details">
              <p><strong>Tópico:</strong> "{currentTopic}"</p>
              <p><strong>Agentes:</strong> {getAgentInfo(agentA).name} vs {getAgentInfo(agentB).name}</p>
              <p><strong>Rodadas:</strong> Máximo de {maxRounds}</p>
            </div>
          </div>
        </div>
      )}

      <div className="debate-info">
        <h5>Como funciona:</h5>
        <ul>
          <li>Os agentes debaterão automaticamente sobre o tópico</li>
          <li>Cada agente responde por vez em rodadas alternadas</li>
          <li>O debate para ao atingir o limite de rodadas</li>
          <li>Você pode interromper a qualquer momento</li>
        </ul>
      </div>
    </div>
  );
};

export default LLMDebateControls;
