import { useState } from 'react'
import { Cloud, Cpu, PanelLeft, SquarePen } from 'lucide-react'

import { useAgentInfo } from '@/modules/chat/api/agent-api'

import { ChatComposer } from '@/modules/chat/components/chat-composer'
import { ChatSidebar } from '@/modules/chat/components/chat-sidebar'
import { ChatThread } from '@/modules/chat/components/chat-thread'
import { ChatWelcome } from '@/modules/chat/components/chat-welcome'
import { useChat } from '@/modules/chat/hooks/use-chat'
import type { OAuthNotice } from '@/modules/auth/lib/oauth-notice'
import type { User } from '@/modules/auth/types'

export function ChatPage({ user, notice }: { user: User; notice: OAuthNotice | null }) {
  const chat = useChat(user.id)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const messages = chat.activeConversation?.messages ?? []
  const { data: info } = useAgentInfo()

  const closeSidebarAnd = (action: () => void) => () => {
    action()
    setSidebarOpen(false)
  }

  return (
    <div className="flex h-dvh bg-white text-slate-900">
      <ChatSidebar
        user={user}
        notice={notice}
        conversations={chat.conversations}
        activeId={chat.activeConversation?.id ?? null}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onNewChat={closeSidebarAnd(chat.startNewChat)}
        onSelect={(id) => closeSidebarAnd(() => chat.selectConversation(id))()}
        onDelete={chat.deleteConversation}
      />

      <main className="setu-canvas flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-2 border-b border-brand-100/70 bg-white/60 px-3 backdrop-blur sm:px-5">
          <button type="button" onClick={() => setSidebarOpen(true)} className="rounded-lg p-2 text-slate-500 hover:bg-brand-50 lg:hidden" aria-label="Open sidebar">
            <PanelLeft className="size-5" />
          </button>
          <h2 className="truncate text-[15px] font-semibold text-slate-800">{chat.activeConversation?.title ?? 'New chat'}</h2>
          {info && (
            <span className="ml-auto hidden items-center gap-1.5 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-medium text-brand-800 shadow-sm sm:inline-flex">
              {info.provider === 'ollama' ? <Cpu className="size-3.5 text-brand-600" /> : <Cloud className="size-3.5 text-brand-600" />}
              {info.model}
            </span>
          )}
          <button type="button" onClick={chat.startNewChat} className="ml-auto sm:ml-2 rounded-lg p-2 text-slate-500 hover:bg-brand-50 lg:hidden" aria-label="New chat">
            <SquarePen className="size-5" />
          </button>
        </header>

        {messages.length === 0 ? <ChatWelcome onSelect={chat.sendMessage} /> : <ChatThread messages={messages} onRetry={chat.retryLast} />}

        <ChatComposer isStreaming={chat.isStreaming} onSend={chat.sendMessage} onStop={chat.stop} autoFocusKey={chat.activeConversation?.id ?? null} />
      </main>
    </div>
  )
}
