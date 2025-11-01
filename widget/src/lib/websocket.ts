import { ChatMessage, ChatConfig, WebSocketEventHandlers, ConnectionStatus } from './types';
import { useEffect, useRef } from 'react';

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private config: ChatConfig;
  private eventHandlers: WebSocketEventHandlers;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private isManualClose = false;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private connectionStatus: ConnectionStatus = {
    isConnected: false,
    isConnecting: false,
    isReconnecting: false,
    lastError: undefined
  };

  constructor(config: ChatConfig, eventHandlers: WebSocketEventHandlers) {
    this.config = config;
    this.eventHandlers = eventHandlers;
  }

  async connect(token: string = 'guest'): Promise<void> {
    if (this.isManualClose) return;

    this.connectionStatus.isConnecting = true;
    this.connectionStatus.isReconnecting = this.reconnectAttempts > 0;

    try {
      const url = new URL(this.config.serverUrl);
      url.searchParams.append('token', token);
      url.searchParams.append('room', this.config.roomId);
      url.searchParams.append('user_id', this.config.user.id);
      url.searchParams.append('user_name', this.config.user.name);

      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => this.handleOpen();
      this.ws.onmessage = (event) => this.handleMessage(event);
      this.ws.onclose = (event) => this.handleClose(event);
      this.ws.onerror = (error) => this.handleError(error);

    } catch (error: any) {
      console.error('WebSocket connection error:', error);
      this.connectionStatus.isConnecting = false;
      this.eventHandlers.onError(`Erro de conexão: ${error.message || error}`);
      this.attemptReconnect(token);
    }
  }

  disconnect(): void {
    console.log('WebSocketManager: disconnect() chamado');
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
      this.eventHandlers.onError('Não conectado ao servidor');
      return;
    }

    if (content.length > 1000) {
      this.eventHandlers.onError('Mensagem muito longa (máx. 1000 caracteres)', 'message_too_long');
      return;
    }

    const message: ChatMessage = {
      type: 'message',
      room: this.config.roomId,
      user: this.config.user,
      content,
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

  changeRoom(newRoomId: string): void {
    if (this.config.roomId === newRoomId) return;

    this.config.roomId = newRoomId;
    this.disconnect();
    this.isManualClose = false;
    this.reconnectAttempts = 0;

    setTimeout(() => {
      this.connect('guest');
    }, 100);
  }

  getConnectionStatus(): ConnectionStatus {
    return { ...this.connectionStatus };
  }

  private handleOpen(): void {
    console.log('WebSocket conectado');
    this.connectionStatus.isConnected = true;
    this.connectionStatus.isConnecting = false;
    this.connectionStatus.isReconnecting = false;
    this.reconnectAttempts = 0;

    if (this.reconnectAttempts > 0) {
      this.eventHandlers.onReconnect?.();
    }
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const message: ChatMessage = JSON.parse(event.data);

      if (!this.validateMessage(message)) {
        console.warn('Mensagem inválida recebida:', message);
        return;
      }

      switch (message.type) {
        case 'message':
          this.eventHandlers.onMessage?.(message);
          break;

        case 'presence':
          const data = message.meta || message.content;
          this.eventHandlers.onPresenceUpdate?.(
            data?.users || [],
            data?.online_count || 0
          );
          break;

        case 'typing':
          this.eventHandlers.onTypingIndicator?.(
            message.user,
            message.content === 'started'
          );
          break;

        case 'system':
          this.eventHandlers.onSystemMessage?.(message.content || '');
          break;

        case 'error':
          this.eventHandlers.onError?.(message.content || 'Erro', message.meta?.code);
          break;

        default:
          console.warn('Tipo de mensagem desconhecido:', message.type);
      }
    } catch (error) {
      console.error('Erro ao processar mensagem:', error);
    }
  }

  private validateMessage(message: any): message is ChatMessage {
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

  private handleClose(event: CloseEvent): void {
    console.log('WebSocket fechado:', { code: event.code, reason: event.reason });

    this.connectionStatus.isConnected = false;
    this.connectionStatus.isConnecting = false;

    const permanentCodes = [1000, 1001, 1008, 1009, 1011, 4000];
    const shouldNotReconnect = permanentCodes.includes(event.code) || this.isManualClose;

    if (!shouldNotReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.attemptReconnect();
    } else {
      this.connectionStatus.isReconnecting = false;
      this.eventHandlers.onDisconnect?.();

      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        this.eventHandlers.onError?.('Muitas tentativas de reconexão. Verifique sua conexão.', 'max_reconnect');
      } else if (shouldNotReconnect && !this.isManualClose) {
        this.eventHandlers.onError?.(`Conexão fechada: ${event.reason || 'código ' + event.code}`, 'closed');
      }
    }
  }

  private handleError(error: Event): void {
    console.error('WebSocket error:', error);
    this.connectionStatus.lastError = 'Erro de conexão';
    this.eventHandlers.onError?.('Erro de conexão com o servidor', 'connection_error');
  }

  private attemptReconnect(token: string = 'guest'): void {
    if (this.isManualClose) return;

    this.connectionStatus.isReconnecting = true;
    this.reconnectAttempts++;

    const delay = Math.min(
      this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
      30000
    );

    console.log(`Tentando reconectar em ${delay}ms (tentativa ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);

    this.reconnectTimeout = setTimeout(() => {
      if (!this.isManualClose) {
        this.connect(token);
      }
    }, delay);
  }
}

// Hook React CORRIGIDO — usa singleton com useRef
export const useWebSocket = (
  config: ChatConfig,
  eventHandlers: WebSocketEventHandlers
): WebSocketManager | null => {
  const managerRef = useRef<WebSocketManager | null>(null);

  useEffect(() => {
    // Cria apenas uma vez
    if (!managerRef.current) {
      managerRef.current = new WebSocketManager(config, eventHandlers);
      managerRef.current.connect('guest');
    } else {
      // Atualiza config se mudou
      managerRef.current['config'] = config;
    }

    return () => {
      // NÃO desconecta aqui — só no unmount do widget
      // managerRef.current?.disconnect();
    };
  }, [config]); // NÃO inclui eventHandlers

  // Atualiza handlers se mudarem (raro com useCallback)
  useEffect(() => {
    if (managerRef.current) {
      managerRef.current['eventHandlers'] = eventHandlers;
    }
  }, [eventHandlers]);

  return managerRef.current;
};
