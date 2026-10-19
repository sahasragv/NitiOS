import type { ChatHistoryMessage, ChatMessage, ChatStreamEvent, Conversation } from '@/modules/chat/types'

/** Prior messages sent with each turn; older ones are dropped to keep the model's context small. */
const MAX_HISTORY_MESSAGES = 20
const MAX_TITLE_LENGTH = 48

export function createId(): string {
  return crypto.randomUUID()
}

export function messageText(message: ChatMessage): string {
  return message.parts
    .flatMap((part) => (part.type === 'text' ? [part.text] : []))
    .join('')
    .trim()
}

export function conversationTitle(firstMessage: string): string {
  const singleLine = firstMessage.replace(/\s+/g, ' ').trim()
  return singleLine.length > MAX_TITLE_LENGTH ? `${singleLine.slice(0, MAX_TITLE_LENGTH - 1)}…` : singleLine
}

/** Convert the visible conversation into the history the backend expects, skipping failed replies. */
export function toHistory(messages: ChatMessage[]): ChatHistoryMessage[] {
  return messages
    .filter((message) => message.role === 'user' || message.status === 'complete' || message.status === 'stopped')
    .map((message) => ({ role: message.role, content: messageText(message) }))
    .filter((message) => message.content.length > 0)
    .slice(-MAX_HISTORY_MESSAGES)
}

/** Apply one stream event to an assistant message. Pure, so it is safe inside React state updaters. */
export function applyStreamEvent(message: ChatMessage, event: ChatStreamEvent): ChatMessage {
  switch (event.type) {
    case 'text_delta': {
      const last = message.parts.at(-1)
      if (last?.type === 'text') {
        return { ...message, parts: [...message.parts.slice(0, -1), { ...last, text: last.text + event.text }] }
      }
      return { ...message, parts: [...message.parts, { type: 'text', text: event.text }] }
    }
    case 'tool_started':
      return {
        ...message,
        parts: [...message.parts, { type: 'tool', id: event.id, name: event.name, arguments: event.arguments, status: 'running' }],
      }
    case 'tool_finished':
      return {
        ...message,
        parts: message.parts.map((part) =>
          part.type === 'tool' && part.id === event.id
            ? { ...part, status: event.is_error ? 'error' : 'success', output: event.output }
            : part,
        ),
      }
    case 'completed': {
      const hasText = message.parts.some((part) => part.type === 'text' && part.text.trim())
      if (hasText) return { ...message, status: 'complete' }
      if (event.result.content) {
        return { ...message, status: 'complete', parts: [...message.parts, { type: 'text', text: event.result.content }] }
      }
      return { ...message, status: 'error', error: 'Setu didn’t produce an answer.' }
    }
    case 'error':
      return { ...message, status: 'error', error: event.message }
  }
}

/** Interrupted streams cannot resume after a reload, so mark them stopped. */
export function settleInterruptedMessages(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((message) =>
      message.status === 'streaming' ? { ...message, status: 'stopped' } : message,
    ),
  }
}
