import React from 'react'
import ReactDOM from 'react-dom/client'
import ChatWidget from './components/ChatBubble'
declare global {
  interface Window {
    InovationAIChatWidget: any
  }
}

class InovationAIChatWidget {
  private config: any;
  
  constructor(config: any) {
    this.config = {
      serverUrl: config.serverUrl || "ws://localhost:8000/ws",
      roomId: config.roomId || "general", 
      user: config.user || { id: 'guest', name: 'Convidado' },
      theme: config.theme || 'auto',
      availableRooms: config.availableRooms || [
        { id: 'general', name: 'Geral', icon: '💬', description: 'Conversas gerais' },
        { id: 'support', name: 'Suporte', icon: '🛟', description: 'Ajuda e suporte' },
        { id: 'sales', name: 'Vendas', icon: '💰', description: 'Consultoria comercial' },
        { id: 'tech', name: 'Tecnologia', icon: '⚡', description: 'Assuntos técnicos' }
      ]
    };
    
    this.initializeWidget();
  }

  private initializeWidget() {
    if (document.getElementById('inovation-ai-chat-widget')) {
      console.warn('Widget já está inicializado');
      return;
    }

    const container = document.createElement('div')
    container.id = 'inovation-ai-chat-widget'
    document.body.appendChild(container)

    ReactDOM.createRoot(container).render(
      <React.StrictMode>
        <ChatWidget config={this.config} />
      </React.StrictMode>
    )
  }
}

window.InovationAIChatWidget = InovationAIChatWidget

if (import.meta.env.DEV) {
  document.addEventListener('DOMContentLoaded', () => {
    new InovationAIChatWidget({
      serverUrl: "ws://localhost:8000/ws",
      roomId: "general",
      user: { 
        id: crypto.randomUUID(), 
        name: "Usuário Demo" 
      },
      theme: "auto"
    });
  });
}
