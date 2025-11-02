import React, { useState, useEffect, useRef } from 'react';
import LLMDebateControls from './LLMDebateControls';
import { ChatConfig, ChatMessage, User, ConnectionStatus, DebateStatus } from '../types';
import './ChatWindow.css';

interface ChatWindowProps {
  config: ChatConfig;
  messages: ChatMessage[];
  onlineCount: number;
  typingUsers: User[];
  debateStatus: DebateStatus;
  connectionStatus: ConnectionStatus;
  onClose: () => void;
  onMinimize: () => void;
  onMaximize: () => void;
  isMinimized: boolean;
  onSendMessage: (content: string) => void;
  onTypingIndicator: (isTyping: boolean) => void;
  onRoomChange: (roomId: string) => void;
  onStartDebate: (topic: string, agentA: string, agentB: string) => void;
  onStopDebate: () => void;
}

const ChatWindow: React.FC<ChatWindowProps> = ({ 
  config, 
  messages, 
  onlineCount, 
  typingUsers, 
  debateStatus,
  connectionStatus,
  onClose, 
  onMinimize,
  onMaximize,
  isMinimized,
  onSendMessage,
  onTypingIndicator,
  onRoomChange,
  onStartDebate,
  onStopDebate
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const [showRoomSelector, setShowRoomSelector] = useState(false);
  const [showLLMControls, setShowLLMControls] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout>();
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const availableRooms = config.availableRooms || [
    { id: 'general', name: 'Geral', icon: '💬', description: 'Conversas gerais' },
    { id: 'support', name: 'Suporte', icon: '🛟', description: 'Ajuda e suporte' },
    { id: 'sales', name: 'Vendas', icon: '💰', description: 'Consultoria comercial' },
    { id: 'tech', name: 'Tecnologia', icon: '⚡', description: 'Assuntos técnicos' }
  ];

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [inputMessage]);

  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(`chat_messages_${config.roomId}`, JSON.stringify(messages));
    }
  }, [messages, config.roomId]);

  useEffect(() => {
    const saved = localStorage.getItem(`chat_messages_${config.roomId}`);
    if (saved) {
      try {
        // Mensagens carregadas do localStorage
        JSON.parse(saved);
      } catch (error) {
        console.error('Erro ao carregar mensagens do localStorage:', error);
      }
    }
  }, [config.roomId]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isMinimized) return;

      switch (e.key) {
        case 'Escape':
          if (showRoomSelector) {
            setShowRoomSelector(false);
          } else if (showLLMControls) {
            setShowLLMControls(false);
          } else {
            onMinimize();
          }
          break;
        case 'ArrowUp':
        case 'ArrowDown':
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isMinimized, showRoomSelector, showLLMControls, onMinimize]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSendMessage = () => {
    if (inputMessage.trim() === '') return;

    onSendMessage(inputMessage);
    setInputMessage('');
    stopTypingIndicator();
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter') {
      if (e.shiftKey) {
        return;
      } else {
        e.preventDefault();
        handleSendMessage();
      }
    }
  };

  const startTypingIndicator = () => {
    if (inputMessage.trim() === '') {
      stopTypingIndicator();
      return;
    }

    if (!isTyping) {
      setIsTyping(true);
      onTypingIndicator(true);
    }

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    typingTimeoutRef.current = setTimeout(stopTypingIndicator, 3000);
  };

  const stopTypingIndicator = () => {
    if (isTyping) {
      setIsTyping(false);
      onTypingIndicator(false);
    }

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputMessage(e.target.value);
    startTypingIndicator();
  };

  const handleRoomChange = (roomId: string) => {
    if (roomId !== config.roomId) {
      onRoomChange(roomId);
      setShowRoomSelector(false);
    }
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getCurrentRoom = () => {
    return availableRooms.find(room => room.id === config.roomId) || availableRooms[0];
  };

  const getTypingText = () => {
    if (typingUsers.length === 0) return '';
    const names = typingUsers.map(user => user.name);
    if (names.length === 1) return `${names[0]} está digitando...`;
    if (names.length === 2) return `${names[0]} e ${names[1]} estão digitando...`;
    return `${names.length} pessoas estão digitando...`;
  };

  const isAgentMessage = (message: ChatMessage) => {
    return message.user.id.startsWith('agent:') || 
           message.user.name.includes('GPT') || 
           message.user.name.includes('Gemini') ||
           message.user.name.includes('Claude') ||
           message.user.name.includes('Agente');
  };

  const getAgentBadge = (message: ChatMessage) => {
    if (isAgentMessage(message)) {
      return '🤖 Agente';
    }
    return null;
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      
      if (showRoomSelector && !target.closest('.room-selector-btn') && !target.closest('.rooms-dropdown')) {
        setShowRoomSelector(false);
      }
      
      if (showLLMControls && !target.closest('.llm-controls-btn') && !target.closest('.llm-debate-section')) {
        setShowLLMControls(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showRoomSelector, showLLMControls]);

  if (isMinimized) {
    return (
      <div className={`chat-window minimized ${config.theme || 'light'}`}>
        <div className="chat-header">
          <div className="header-content">
            <div className="header-left">
              <button 
                className="room-selector-btn"
                onClick={onMaximize}
                aria-label="Maximizar chat"
              >
                <span className="room-icon">{getCurrentRoom().icon}</span>
                <div className="room-details">
                  <span className="room-title">{getCurrentRoom().name}</span>
                  <span className="room-status">
                    <div className={`status-dot ${connectionStatus.isConnected ? 'connected' : 'disconnected'}`}></div>
                    {connectionStatus.isConnected ? `${onlineCount} online` : 'Desconectado'}
                  </span>
                </div>
              </button>
            </div>

            <div className="header-right">
              <button 
                className="maximize-btn"
                onClick={onMaximize}
                aria-label="Maximizar chat"
                title="Maximizar"
              >
                <svg viewBox="0 0 24 24" width="20">
                  <path fill="currentColor" d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
                </svg>
              </button>

              <button className="close-btn" onClick={onClose} aria-label="Fechar chat" title="Fechar">
                <svg viewBox="0 0 24 24" width="20">
                  <path stroke="currentColor" strokeWidth="2" d="M18 6L6 18M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`chat-window ${config.theme || 'light'}`}
      role="dialog"
      aria-label="Janela de chat"
      aria-modal="true"
    >
      <div className="chat-header">
        <div className="header-content">
          <div className="header-left">
            <button 
              className="room-selector-btn"
              onClick={() => setShowRoomSelector(!showRoomSelector)}
              aria-expanded={showRoomSelector}
              aria-haspopup="true"
              aria-label={`Sala atual: ${getCurrentRoom().name}. Clique para mudar de sala`}
            >
              <span className="room-icon" aria-hidden="true">{getCurrentRoom().icon}</span>
              <div className="room-details">
                <span className="room-title">{getCurrentRoom().name}</span>
                <span className="room-status">
                  <div 
                    className={`status-dot ${connectionStatus.isConnected ? 'connected' : connectionStatus.isReconnecting ? 'reconnecting' : 'disconnected'}`}
                    aria-hidden="true"
                  ></div>
                  {connectionStatus.isConnected ? `${onlineCount} online` : 
                   connectionStatus.isReconnecting ? 'Reconectando...' : 'Desconectado'}
                </span>
              </div>
              <svg 
                className={`chevron ${showRoomSelector ? 'rotated' : ''}`} 
                viewBox="0 0 24 24" 
                width="16"
                aria-hidden="true"
              >
                <path fill="currentColor" d="M7 10l5 5 5-5z"/>
              </svg>
            </button>
          </div>

          <div className="header-right">
            <button 
              className={`llm-controls-btn ${debateStatus.isActive ? 'active' : ''}`}
              onClick={() => setShowLLMControls(!showLLMControls)}
              aria-expanded={showLLMControls}
              aria-label="Controles de debate entre LLMs"
              title="Controles LLM"
            >
              <svg viewBox="0 0 24 24" width="20" aria-hidden="true">
                <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 15h2v2h-2zm0-8h2v6h-2z"/>
              </svg>
              {debateStatus.isActive && <span className="debate-active-dot" aria-hidden="true"></span>}
            </button>

            <button 
              className="minimize-btn"
              onClick={onMinimize}
              aria-label="Minimizar chat"
              title="Minimizar"
            >
              <svg viewBox="0 0 24 24" width="20" aria-hidden="true">
                <path fill="currentColor" d="M19 13H5v-2h14v2z"/>
              </svg>
            </button>

            <button 
              className="close-btn" 
              onClick={onClose} 
              aria-label="Fechar chat"
              title="Fechar"
            >
              <svg viewBox="0 0 24 24" width="20" aria-hidden="true">
                <path stroke="currentColor" strokeWidth="2" d="M18 6L6 18M6 6l12 12"/>
              </svg>
            </button>
          </div>
        </div>

        {showRoomSelector && (
          <div 
            className="rooms-dropdown"
            role="menu"
            aria-label="Selecionar sala"
          >
            <div className="dropdown-header">
              <h4>Mudar de sala</h4>
              <p>Escolha uma sala para conversar</p>
            </div>
            <div className="rooms-list">
              {availableRooms.map(room => (
                <button
                  key={room.id}
                  className={`room-item ${room.id === config.roomId ? 'active' : ''}`}
                  onClick={() => handleRoomChange(room.id)}
                  role="menuitemradio"
                  aria-checked={room.id === config.roomId}
                >
                  <span className="item-icon" aria-hidden="true">{room.icon}</span>
                  <div className="item-info">
                    <span className="item-name">{room.name}</span>
                    <span className="item-desc">{room.description}</span>
                  </div>
                  {room.id === config.roomId && (
                    <div className="active-check" aria-hidden="true">
                      <svg viewBox="0 0 24 24" width="16">
                        <path fill="currentColor" d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                      </svg>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {debateStatus.isActive && (
        <div 
          className="debate-status-bar"
          role="status"
          aria-live="polite"
          aria-atomic="true"
        >
          <div className="debate-info">
            <span className="debate-badge">🤖 DEBATE ATIVO</span>
            <span className="debate-topic">{debateStatus.topic}</span>
            {debateStatus.currentRound && (
              <span className="debate-round">Rodada {debateStatus.currentRound}/{debateStatus.maxRounds}</span>
            )}
          </div>
        </div>
      )}

      <div 
        className="messages-container" 
        ref={messagesContainerRef}
        role="log"
        aria-label="Mensagens do chat"
        tabIndex={0}
      >
        {messages.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon" aria-hidden="true">💬</div>
            <h3>Nenhuma mensagem ainda</h3>
            <p>Seja o primeiro a enviar uma mensagem nesta sala!</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div 
              key={`${message.client_id || index}-${message.ts}`} 
              className={`message ${message.user.id === config.user.id ? 'own-message' : ''} ${message.type} ${isAgentMessage(message) ? 'agent-message' : ''}`}
              role="article"
              aria-label={`Mensagem de ${message.user.name} às ${formatTime(message.ts)}`}
            >
              {message.type === 'system' ? (
                <div className="system-message" role="status">
                  <span>{message.content}</span>
                </div>
              ) : message.type === 'error' ? (
                <div className="error-message" role="alert">
                  <span>⚠️ {message.content}</span>
                </div>
              ) : (
                <>
                  <div className="message-avatar" aria-hidden="true">
                    {message.user.avatar ? (
                      <img src={message.user.avatar} alt="" />
                    ) : (
                      <div className="avatar-placeholder">
                        {isAgentMessage(message) ? '🤖' : message.user.name.charAt(0).toUpperCase()}
                      </div>
                    )}
                  </div>
                  <div className="message-content">
                    <div className="message-header">
                      <span className="user-name">
                        {message.user.name}
                        {getAgentBadge(message) && (
                          <span className="agent-badge">{getAgentBadge(message)}</span>
                        )}
                      </span>
                      <span className="message-time">{formatTime(message.ts)}</span>
                    </div>
                    <div className="message-text">{message.content}</div>
                  </div>
                </>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} className="messages-anchor" aria-hidden="true" />
      </div>

      {typingUsers.length > 0 && (
        <div 
          className="typing-indicator"
          role="status"
          aria-live="polite"
          aria-label={getTypingText()}
        >
          <div className="typing-dots" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span className="typing-text">{getTypingText()}</span>
        </div>
      )}

      {showLLMControls && (
        <div className="llm-debate-section">
          <LLMDebateControls
            onStartDebate={onStartDebate}
            onStopDebate={onStopDebate}
            isDebateActive={debateStatus.isActive}
            currentTopic={debateStatus.topic}
          />
        </div>
      )}

      <div className="input-container">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={inputMessage}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            placeholder={`Enviar mensagem em ${getCurrentRoom().name}... (Shift+Enter para nova linha)`}
            className="message-input"
            rows={1}
            onFocus={() => startTypingIndicator()}
            onBlur={() => stopTypingIndicator()}
            aria-label="Digite sua mensagem"
            aria-describedby="input-instructions"
          />
          <button 
            onClick={handleSendMessage} 
            disabled={!inputMessage.trim()}
            className="send-btn"
            aria-label="Enviar mensagem"
          >
            <svg viewBox="0 0 24 24" width="20" aria-hidden="true">
              <path fill="currentColor" d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
            </svg>
          </button>
        </div>
        <div id="input-instructions" className="sr-only">
          Pressione Enter para enviar, Shift+Enter para nova linha
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
