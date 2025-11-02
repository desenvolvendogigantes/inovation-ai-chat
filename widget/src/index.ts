export { default as ChatWidget } from './components/ChatBubble'
export type { ChatBubbleProps } from './components/ChatBubble'

export type {
  ChatMessage,
  ChatConfig,
  User,
  Room,
  LLMAgent,
  LLMDebateInfo,
  DebateConfig,
  DebateStatus,
  WebSocketEventHandlers,
  ConnectionStatus
} from './types'

export { WebSocketManager, useWebSocket } from './lib/WebSocketManager'
