import { 
  ChatMessage, 
  ChatConfig, 
  WebSocketEventHandlers, 
  ConnectionStatus,
  DebateConfig,
  LLMDebateInfo,
  User 
} from '../types';
import { useEffect, useRef } from 'react';

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private config: ChatConfig;
  private eventHandlers: WebSocketEventHandlers;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseReconnectDelay = 1000;
  private isManualClose = false;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private messageQueue: ChatMessage[] = [];
  
  public connectionStatus: ConnectionStatus = {
    isConnected: false,
    isConnecting: false,
    isReconnecting: false
  };

  constructor(config: ChatConfig, eventHandlers: WebSocketEventHandlers) {
    this.config = config;
    this.eventHandlers = eventHandlers;
  }

  connect(): void {
    if (this.isManualClose) return;
    
    this.connectionStatus.isConnecting = true;
    this.connectionStatus.isReconnecting = this.reconnectAttempts > 0;

    try {
      const url = new URL(this.config.serverUrl);
      url.searchParams.append('room', this.config.roomId);
      url.searchParams.append('user_id', this.config.user.id);
      url.searchParams.append('user_name', this.config.user.name);
      url.searchParams.append('token', this.config.token || 'guest');

      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => this.handleOpen();
      this.ws.onmessage = (event) => this.handleMessage(event);
      this.ws.onclose = (event) => this.handleClose(event);
      this.ws.onerror = (error) => this.handleError(error);

    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.eventHandlers.onError?.(`Erro de conexão: ${error}`);
      this.scheduleReconnect();
    }
  }

  disconnect(): void {
    this.isManualClose = true;
    this.reconnectAttempts = 0;
    this.connectionStatus.isConnected = false;
    this.connectionStatus.isConnecting = false;
    this.connectionStatus.isReconnecting = false;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.ws) {
      this.ws.close(1000, 'Manual disconnect');
      this.ws = null;
    }
  }

  public isManuallyDisconnected(): boolean {
    return this.isManualClose;
  }

  sendMessage(content: string, clientId?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.eventHandlers.onError?.('Não conectado ao servidor');
      return;
    }

    if (content.length > 1000) {
      this.eventHandlers.onError?.('Mensagem muito longa (máximo 1000 caracteres)', 'message_too_long');
      return;
    }

    const sanitizedContent = content.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    
    const message: ChatMessage = {
      type: 'message',
      room: this.config.roomId,
      user: this.config.user,
      content: sanitizedContent,
      ts: Date.now(),
      client_id: clientId || crypto.randomUUID(),
      meta: {}
    };

    this.ws.send(JSON.stringify(message));
  }

  sendTypingIndicator(isTyping: boolean): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const message: ChatMessage = {
      type: 'typing',
      room: this.config.roomId,
      user: this.config.user,
      content: isTyping ? 'started' : 'stopped',
      ts: Date.now(),
      client_id: null,
      meta: { ttl: 5000 }
    };

    this.ws.send(JSON.stringify(message));
  }

  startLLMDebate(topic: string, agentA: string, agentB: string, maxRounds: number = 6): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.eventHandlers.onError?.('Não conectado ao servidor');
      return;
    }

    const sanitizedTopic = topic.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

    const message: ChatMessage = {
      type: 'system',
      room: this.config.roomId,
      user: this.config.user,
      content: 'Iniciando debate LLM',
      ts: Date.now(),
      client_id: null,
      meta: {
        action: 'llm_debate_start',
        topic: sanitizedTopic,
        agent_a: agentA,
        agent_b: agentB,
        max_rounds: maxRounds,
        max_duration: 90000
      }
    };

    this.ws.send(JSON.stringify(message));
  }

  stopLLMDebate(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const message: ChatMessage = {
      type: 'system',
      room: this.config.roomId,
      user: this.config.user,
      content: 'Parando debate LLM',
      ts: Date.now(),
      client_id: null,
      meta: { action: 'llm_debate_stop' }
    };

    this.ws.send(JSON.stringify(message));
  }

  changeRoom(newRoomId: string): void {
    if (this.config.roomId === newRoomId) return;

    this.sendSystemEvent('leave');
    this.config.roomId = newRoomId;
    this.disconnect();
    this.isManualClose = false;
    this.reconnectAttempts = 0;

    setTimeout(() => this.connect(), 100);
  }

  private sendSystemEvent(action: 'join' | 'leave'): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    const message: ChatMessage = {
      type: 'system',
      room: this.config.roomId,
      user: this.config.user,
      content: action === 'join' ? 'entered' : 'left',
      ts: Date.now(),
      client_id: null,
      meta: { action }
    };

    this.ws.send(JSON.stringify(message));
  }

  private handleOpen(): void {
    this.connectionStatus.isConnected = true;
    this.connectionStatus.isConnecting = false;
    this.connectionStatus.isReconnecting = false;
    this.reconnectAttempts = 0;

    this.processMessageQueue();
    this.sendSystemEvent('join');
    this.eventHandlers.onReconnect?.();
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: ChatMessage = JSON.parse(event.data);
      if (!this.validateMessageFormat(message)) return;

      switch (message.type) {
        case 'message':
          this.handleRegularMessage(message);
          break;
        case 'presence':
          this.handlePresenceMessage(message);
          break;
        case 'typing':
          this.handleTypingMessage(message);
          break;
        case 'system':
          this.handleSystemMessage(message);
          break;
        case 'error':
          this.handleErrorMessage(message);
          break;
      }
    } catch (error) {
      console.error('Erro ao processar mensagem:', error);
      this.eventHandlers.onError?.('Erro ao processar mensagem do servidor', 'parse_error');
    }
  }

  private validateMessageFormat(message: any): boolean {
    return (
      message &&
      typeof message === 'object' &&
      ['message', 'presence', 'typing', 'system', 'error'].includes(message.type) &&
      typeof message.room === 'string' &&
      message.user &&
      typeof message.user.id === 'string' &&
      typeof message.user.name === 'string' &&
      typeof message.ts === 'number'
    );
  }

  private handleRegularMessage(message: ChatMessage): void {
    if (message.content) {
      message.content = message.content.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
    }
    this.eventHandlers.onMessage?.(message);
  }

  private handlePresenceMessage(message: ChatMessage): void {
    const users = message.meta?.users || [];
    const onlineCount = message.meta?.online_count || 0;
    const validUsers = users.filter((u: any) => u?.id && u?.name);
    this.eventHandlers.onPresenceUpdate?.(validUsers, onlineCount);
  }

  private handleTypingMessage(message: ChatMessage): void {
    if (message.user.id === this.config.user.id) return;
    this.eventHandlers.onTypingIndicator?.(message.user, message.content === 'started');
  }

  private handleSystemMessage(message: ChatMessage): void {
    const meta = message.meta as LLMDebateInfo;
    if (meta?.action?.startsWith('llm_debate_')) {
      this.handleLLMDebateSystemMessage(message, meta);
    } else {
      this.eventHandlers.onSystemMessage?.(message.content || '', message.meta);
    }
  }

  private handleLLMDebateSystemMessage(message: ChatMessage, meta: LLMDebateInfo): void {
    switch (meta.action) {
      case 'llm_debate_started':
        this.eventHandlers.onLLMDebateStart?.({
          topic: meta.topic!,
          agentA: meta.agent_a!,
          agentB: meta.agent_b!,
          maxRounds: meta.max_rounds,
          maxDuration: meta.max_duration
        });
        break;
      case 'llm_debate_round':
        this.eventHandlers.onLLMDebateUpdate?.(meta.current_round!, meta.current_agent!);
        break;
      case 'llm_debate_stopped':
        this.eventHandlers.onLLMDebateStop?.(meta.reason);
        break;
      case 'llm_debate_error':
        this.eventHandlers.onError?.(meta.error_message || 'Erro no debate LLM', 'llm_error');
        break;
    }
    this.eventHandlers.onSystemMessage?.(message.content || '', message.meta);
  }

  private handleErrorMessage(message: ChatMessage): void {
    const code = message.meta?.code;
    const msg = message.content || 'Erro desconhecido';
    this.eventHandlers.onError?.(code === 'rate_limited' ? 'Muitas mensagens em pouco tempo.' : msg, code);
  }

  private handleClose(event: CloseEvent): void {
    this.connectionStatus.isConnected = false;
    this.connectionStatus.isConnecting = false;

    const permanent = [1000, 1002, 1003, 1008, 1009, 4000].includes(event.code) || this.isManualClose;

    if (!permanent && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.scheduleReconnect();
    } else {
      this.connectionStatus.isReconnecting = false;
      this.eventHandlers.onDisconnect?.();

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this.eventHandlers.onError?.('Muitas tentativas de reconexão.', 'max_reconnect');
      } else if (permanent && !this.isManualClose) {
        this.eventHandlers.onError?.(`Conexão fechada: ${event.reason || 'código ' + event.code}`, 'closed');
      }
    }
  }

  private handleError(error: Event): void {
    this.eventHandlers.onError?.('Erro de conexão com o servidor', 'connection_error');
  }

  private scheduleReconnect(): void {
    this.connectionStatus.isReconnecting = true;
    this.reconnectAttempts++;

    const delay = Math.min(this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);

    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);

    this.reconnectTimeout = setTimeout(() => {
      if (!this.isManualClose) this.connect();
    }, delay);
  }

  private processMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const msg = this.messageQueue.shift();
      if (msg && this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify(msg));
      }
    }
  }

  getConnectionStatus(): ConnectionStatus {
    return { ...this.connectionStatus };
  }

  static isAgentMessage(message: ChatMessage): boolean {
    return (
      message.user.id.startsWith('agent:') || 
      /gpt-|gemini-|claude-/.test(message.user.id) ||
      /GPT|Gemini|Claude/.test(message.user.name)
    );
  }

  static getAgentInfo(message: ChatMessage): { provider: string; model: string; badge: string } {
    const id = message.user.id;
    const name = message.user.name;

    if (id.startsWith('agent:')) {
      const [, provider, model] = id.split(':');
      return { provider: provider || 'unknown', model: model || 'unknown', badge: `Agente ${name}` };
    }
    if (id.includes('gpt-') || name.includes('GPT')) return { provider: 'OpenAI', model: 'GPT', badge: 'GPT' };
    if (id.includes('gemini-') || name.includes('Gemini')) return { provider: 'Google', model: 'Gemini', badge: 'Gemini' };
    if (id.includes('claude-') || name.includes('Claude')) return { provider: 'Anthropic', model: 'Claude', badge: 'Claude' };
    return { provider: 'unknown', model: 'unknown', badge: 'Agente' };
  }
}

export const useWebSocket = (
  config: ChatConfig,
  eventHandlers: WebSocketEventHandlers
): WebSocketManager | null => {
  const managerRef = useRef<WebSocketManager | null>(null);

  useEffect(() => {
    if (!managerRef.current) {
      managerRef.current = new WebSocketManager(config, eventHandlers);
      managerRef.current.connect();
    } else {
      managerRef.current['config'] = config;
    }
  }, [config]);

  useEffect(() => {
    if (managerRef.current) {
      managerRef.current['eventHandlers'] = eventHandlers;
    }
  }, [eventHandlers]);

  return managerRef.current;
};
