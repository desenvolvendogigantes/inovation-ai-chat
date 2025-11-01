export interface User {
  id: string;
  name: string;
  avatar?: string | null;
}

// ChatMessage com campos opcionais para flexibilidade
export interface ChatMessage {
  type: 'message' | 'presence' | 'typing' | 'system' | 'error';
  room: string;
  user: User;
  content: string | null;
  ts: number;
  client_id?: string | null; // ✅ Tornado opcional
  meta?: Record<string, any>;
  code?: string;
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
  icon?: string;
  description?: string;
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

export interface LLMDebateInfo {
  action: 'llm_debate_started' | 'llm_debate_round' | 'llm_debate_stopped' | 'llm_debate_error';
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

export interface DebateConfig {
  topic: string;
  agentA: string;
  agentB: string;
  maxRounds?: number;
  maxDuration?: number;
}

export interface DebateStatus {
  isActive: boolean;
  topic?: string;
  agentA?: string;
  agentB?: string;
  maxRounds?: number;
  currentRound?: number;
  currentAgent?: string;
}

export interface WebSocketEventHandlers {
  onMessage: (message: ChatMessage) => void;
  onPresenceUpdate: (users: User[], onlineCount: number) => void;
  onTypingIndicator: (user: User, isTyping: boolean) => void;
  onSystemMessage: (content: string, meta?: any) => void;
  onError: (error: string, code?: string) => void;
  onReconnect: () => void;
  onDisconnect: () => void;
  onLLMDebateStart: (config: DebateConfig) => void;
  onLLMDebateUpdate: (round: number, currentAgent: string) => void;
  onLLMDebateStop: (reason?: string) => void;
}

export interface ConnectionStatus {
  isConnected: boolean;
  isConnecting: boolean;
  isReconnecting: boolean;
  lastError?: string;
}

export interface ChatBubbleProps {
  config: ChatConfig;
}

export interface ChatWindowProps {
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

export interface LLMDebateControlsProps {
  roomId: string;
  onStartDebate: (topic: string, agentA: string, agentB: string) => void;
  onStopDebate: () => void;
  isDebateActive: boolean;
  currentTopic?: string;
}
