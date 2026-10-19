import { useEffect, useRef } from 'react'

import { ChatMessage } from '@/modules/chat/components/chat-message'
import type { ChatMessage as ChatMessageModel } from '@/modules/chat/types'

export interface ChatThreadProps {
  messages: ChatMessageModel[]
  onRetry: () => void
}

/** Distance from the bottom, in pixels, within which new content keeps the view pinned. */
const STICK_THRESHOLD_PX = 120

export function ChatThread({ messages, onRetry }: ChatThreadProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  useEffect(() => {
    const container = containerRef.current
    if (container && stickToBottom.current) container.scrollTop = container.scrollHeight
  }, [messages])

  const handleScroll = () => {
    const container = containerRef.current
    if (!container) return
    stickToBottom.current = container.scrollHeight - container.scrollTop - container.clientHeight < STICK_THRESHOLD_PX
  }

  return (
    <div ref={containerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-8 sm:px-6">
        {messages.map((message, index) => (
          <ChatMessage key={message.id} message={message} isLast={index === messages.length - 1} onRetry={onRetry} />
        ))}
      </div>
    </div>
  )
}
