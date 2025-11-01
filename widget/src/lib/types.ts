// Tipos principais conforme especificado no PDF
export interface User {
  id: string;
  name: string;
  avatar?: string | null;
}

export interface ChatMessage {
  type: 'message' | 'presence' | 'typing' | 'system' | 'error';
  room: string;
  user: User;
  content: string | null;
  ts: number;
  client_id: string | null;
  meta: Record<string, any>;
}

export interface ChatConfig {
  serverUrl: string;
  roomId: string;
  user: User;
  token?: string;
  theme?: 'light' | 'dark' | 'auto';
  availableRooms?: Room[];
}

export interface Room {
  id: string;
  name: string;
  icon: string;
  description: string;
}

export interface LLMAgent {
  id: string;
  name: string;
  provider: string;
  model: string;
  temperature?: number;
  max_tokens?: number;
  system_prompt?: string;
}

export interface DebateConfig {
  topic: string;
  agentA: string; // agent ID
  agentB: string; // agent ID
  maxRounds?: number;
  maxDuration?: number;
}

export interface LLMDebateInfo {
  action?: 'llm_debate_start' | 'llm_debate_started' | 'llm_debate_round' | 'llm_debate_stopped' | 'llm_debate_error';
  topic?: string;
  agent_a?: string;
  agent_b?: string;
  max_rounds?: number;
  max_duration?: number;
  current_round?: number;
  current_agent?: string;
  reason?: string;
  error_message?: string;
}

export interface WebSocketEventHandlers {
  onMessage: (message: ChatMessage) => void;
  onPresenceUpdate: (users: User[], onlineCount: number) => void;
  onTypingIndicator: (user: User, isTyping: boolean) => void;
  onSystemMessage: (content: string, meta?: Record<string, any>) => void;
  onError: (error: string, code?: string) => void;
  onReconnect: () => void;
  onDisconnect: () => void;
  onLLMDebateStart: (config: DebateConfig) => void;
  onLLMDebateUpdate: (currentRound: number, currentAgent: string) => void;
  onLLMDebateStop: (reason?: string) => void;
}

export interface ConnectionStatus {
  isConnected: boolean;
  isConnecting: boolean;
  isReconnecting: boolean;
  lastError?: string;
}

export interface DebateStatus {
  isActive: boolean;
  topic?: string;
  agentA?: string;
  agentB?: string;
  maxRounds?: number;
  currentRound?: number;
}

// Tipos para o widget
export interface WidgetConfig {
  serverUrl: string;
  roomId: string;
  user: User;
  theme?: 'light' | 'dark' | 'auto';
  availableRooms?: Room[];
}

// Tipos para mensagens específicas conforme PDF
export interface PresenceMessage extends ChatMessage {
  type: 'presence';
  meta: {
    users: User[];
    online_count: number;
  };
}

export interface TypingMessage extends ChatMessage {
  type: 'typing';
  content: 'started' | 'stopped';
}

export interface SystemMessage extends ChatMessage {
  type: 'system';
  content: string;
  meta: Record<string, any>;
}

export interface ErrorMessage extends ChatMessage {
  type: 'error';
  content: string;
  meta: {
    code: string;
    [key: string]: any;
  };
}
