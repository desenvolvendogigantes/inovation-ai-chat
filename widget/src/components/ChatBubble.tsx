import React, { useState, useEffect, useRef } from 'react'
import ChatWindow from './ChatWindow'
import { useWebSocket } from '../lib/WebSocketManager'
import { ChatConfig, ChatMessage, User, DebateStatus } from '../types'
import './ChatBubble.css'

export interface ChatBubbleProps {
  config: ChatConfig
}

const ChatBubble: React.FC<ChatBubbleProps> = ({ config }) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [selectedRoom, setSelectedRoom] = useState(config.roomId)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [onlineCount, setOnlineCount] = useState(0)
  const [typingUsers, setTypingUsers] = useState<User[]>([])
  const [debateStatus, setDebateStatus] = useState<DebateStatus>({ isActive: false })

  const chatBubbleRef = useRef<HTMLButtonElement>(null)

  const wsManager = useWebSocket(config, {
    onMessage: (message: ChatMessage) => {
      setMessages(prev => [...prev, message])
      
      if (message.user.id !== config.user.id && (!isOpen || isMinimized)) {
        setUnreadCount(prev => prev + 1)
      }
    },
    
    onPresenceUpdate: (_users: User[], count: number) => {
      setOnlineCount(count)
    },
    
    onTypingIndicator: (user: User, isTyping: boolean) => {
      setTypingUsers(prev => {
        if (isTyping) {
          return [...prev.filter(u => u.id !== user.id), user]
        } else {
          return prev.filter(u => u.id !== user.id)
        }
      })
    },
    
    onSystemMessage: (message: string) => {
      const systemMessage: ChatMessage = {
        type: 'system',
        room: selectedRoom,
        user: { id: 'system', name: 'Sistema' },
        content: message,
        ts: Date.now()
      }
      setMessages(prev => [...prev, systemMessage])
    },
    
    onError: (error: string, code?: string) => {
      console.error('WebSocket error:', error, code)
      const errorMessage: ChatMessage = {
        type: 'error',
        room: selectedRoom,
        user: { id: 'system', name: 'Erro' },
        content: error,
        ts: Date.now(),
        code
      }
      setMessages(prev => [...prev, errorMessage])
    },
    
    onReconnect: () => {
      console.log('Reconectado ao servidor')
    },
    
    onDisconnect: () => {
      console.log('Desconectado do servidor')
    },
    
    onLLMDebateStart: (debateConfig) => {
      setDebateStatus({
        isActive: true,
        topic: debateConfig.topic,
        agentA: debateConfig.agentA,
        agentB: debateConfig.agentB,
        maxRounds: debateConfig.maxRounds
      })
    },
    
    onLLMDebateStop: () => {
      setDebateStatus({ isActive: false })
    },
    
    onLLMDebateUpdate: (round) => {
      setDebateStatus(prev => ({
        ...prev,
        currentRound: round
      }))
    }
  })

  const handleOpenChat = () => {
    if (isMinimized) {
      setIsMinimized(false)
    } else if (!isOpen) {
      setIsOpen(true)
      setUnreadCount(0)
    } else {
      setIsMinimized(true)
    }
  }

  const handleCloseChat = () => {
    setIsOpen(false)
    setIsMinimized(false)
  }

  const handleMinimizeChat = () => {
    setIsMinimized(true)
  }

  const handleMaximizeChat = () => {
    setIsMinimized(false)
  }

  const handleRoomChange = (newRoomId: string) => {
    setSelectedRoom(newRoomId)
    setMessages([])
    setUnreadCount(0)
    setTypingUsers([])
    
    if (wsManager) {
      wsManager.changeRoom(newRoomId)
    }
  }

  const handleSendMessage = (content: string) => {
    if (wsManager && content.trim()) {
      wsManager.sendMessage(content.trim())
    }
  }

  const handleTypingIndicator = (isTyping: boolean) => {
    if (wsManager) {
      wsManager.sendTypingIndicator(isTyping)
    }
  }

  const handleStartDebate = (topic: string, agentA: string, agentB: string) => {
    if (wsManager) {
      wsManager.startLLMDebate(topic, agentA, agentB, 6)
    }
  }

  const handleStopDebate = () => {
    if (wsManager) {
      wsManager.stopLLMDebate()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault()
        handleOpenChat()
        break
      case 'Escape':
        if (isOpen && !isMinimized) {
          e.preventDefault()
          handleMinimizeChat()
        }
        break
    }
  }

  useEffect(() => {
    if (!isOpen && !isMinimized && chatBubbleRef.current) {
      chatBubbleRef.current.focus()
    }
  }, [isOpen, isMinimized])

  return (
    <div className={`chat-widget ${config.theme || 'light'}`}>
      {(isOpen || isMinimized) && (
        <ChatWindow 
          config={{
            ...config,
            roomId: selectedRoom
          }}
          messages={messages}
          onlineCount={onlineCount}
          typingUsers={typingUsers}
          debateStatus={debateStatus}
          connectionStatus={wsManager?.connectionStatus || {
            isConnected: false,
            isConnecting: false,
            isReconnecting: false
          }}
          onClose={handleCloseChat}
          onMinimize={handleMinimizeChat}
          onMaximize={handleMaximizeChat}
          isMinimized={isMinimized}
          onSendMessage={handleSendMessage}
          onTypingIndicator={handleTypingIndicator}
          onRoomChange={handleRoomChange}
          onStartDebate={handleStartDebate}
          onStopDebate={handleStopDebate}
        />
      )}
      
      <button 
        ref={chatBubbleRef}
        className="chat-bubble"
        onClick={handleOpenChat}
        onKeyDown={handleKeyDown}
        aria-label={
          isOpen && !isMinimized ? 'Minimizar chat' :
          isMinimized ? 'Maximizar chat' :
          unreadCount > 0 ? `Abrir chat (${unreadCount} mensagens não lidas)` : 'Abrir chat'
        }
        aria-expanded={isOpen && !isMinimized}
        aria-controls="chat-window"
        title={
          isOpen && !isMinimized ? 'Minimizar chat' :
          isMinimized ? 'Maximizar chat' :
          'Abrir chat'
        }
      >
        <div className="chat-bubble-inner">
          {isOpen && !isMinimized ? (
            <svg className="chat-icon minimize-icon" viewBox="0 0 24 24" fill="none">
              <path 
                d="M19 13H5v-2h14v2z" 
                fill="currentColor"
              />
            </svg>
          ) : isMinimized ? (
            <svg className="chat-icon maximize-icon" viewBox="0 0 24 24" fill="none">
              <path 
                d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" 
                fill="currentColor"
              />
            </svg>
          ) : (
            <svg className="chat-icon default-icon" viewBox="0 0 24 24" fill="none">
              <path 
                d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z" 
                fill="currentColor"
              />
            </svg>
          )}
          
          {unreadCount > 0 && (
            <span className="unread-badge" aria-live="polite" aria-atomic="true">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
        </div>
      </button>
    </div>
  )
}

export default ChatBubble
