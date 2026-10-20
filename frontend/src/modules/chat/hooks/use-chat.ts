import { useCallback, useEffect, useRef, useState } from 'react'

import { generateTitle } from '@/modules/chat/api/agent-api'
import { streamChat } from '@/modules/chat/api/stream-chat'
import { applyStreamEvent, conversationTitle, createId, messageText, toHistory } from '@/modules/chat/lib/messages'
import { loadConversations, saveConversations } from '@/modules/chat/lib/storage'
import type { ChatMessage, Conversation } from '@/modules/chat/types'

const SAVE_DELAY_MS = 400

/** Owns the signed-in user's conversations, the active one, and the in-flight streamed reply. */
export function useChat(userId: string) {
  const [conversations, setConversations] = useState<Conversation[]>(() => loadConversations(userId))
  const [activeId, setActiveId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const titleRequests = useRef(new Set<string>())

  useEffect(() => {
    const timer = window.setTimeout(() => saveConversations(userId, conversations), SAVE_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [userId, conversations])

  useEffect(() => () => abortRef.current?.abort(), [])

  const activeConversation = conversations.find((conversation) => conversation.id === activeId) ?? null

  const updateMessage = useCallback((conversationId: string, messageId: string, update: (message: ChatMessage) => ChatMessage) => {
    setConversations((previous) =>
      previous.map((conversation) =>
        conversation.id === conversationId
          ? { ...conversation, messages: conversation.messages.map((message) => (message.id === messageId ? update(message) : message)) }
          : conversation,
      ),
    )
  }, [])

  /** Replace the conversation's fallback title with a short model-written summary. */
  const requestTitle = useCallback(async (conversationId: string, message: string, reply: string) => {
    if (!message || titleRequests.current.has(conversationId)) return
    titleRequests.current.add(conversationId)
    try {
      const title = await generateTitle(message, reply)
      if (title) {
        setConversations((previous) =>
          previous.map((conversation) => (conversation.id === conversationId ? { ...conversation, title, titleGenerated: true } : conversation)),
        )
      }
    } catch {
      // Keep the fallback title; it is retried the next time the chat is opened.
    } finally {
      titleRequests.current.delete(conversationId)
    }
  }, [])

  /**
   * Stream a reply to `history` into a new assistant message appended to the conversation.
   * When `titleFrom` is given, a short title is requested once the reply completes.
   */
  const streamReply = useCallback(
    async (conversationId: string, history: ChatMessage[], titleFrom?: string) => {
      const assistant: ChatMessage = { id: createId(), role: 'assistant', parts: [], status: 'streaming', createdAt: Date.now() }
      setConversations((previous) =>
        previous.map((conversation) =>
          conversation.id === conversationId
            ? { ...conversation, updatedAt: Date.now(), messages: [...conversation.messages, assistant] }
            : conversation,
        ),
      )

      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)
      let replyText = ''
      let failed = false
      try {
        await streamChat(
          toHistory(history),
          (event) => {
            if (event.type === 'text_delta') replyText += event.text
            if (event.type === 'error') failed = true
            updateMessage(conversationId, assistant.id, (message) => applyStreamEvent(message, event))
          },
          controller.signal,
        )
        updateMessage(conversationId, assistant.id, (message) => (message.status === 'streaming' ? { ...message, status: 'complete' } : message))
        if (titleFrom && !failed) void requestTitle(conversationId, titleFrom, replyText)
      } catch (error) {
        updateMessage(conversationId, assistant.id, (message) =>
          controller.signal.aborted
            ? { ...message, status: 'stopped' }
            : { ...message, status: 'error', error: error instanceof Error ? error.message : 'Something went wrong.' },
        )
      } finally {
        if (abortRef.current === controller) abortRef.current = null
        setIsStreaming(false)
      }
    },
    [requestTitle, updateMessage],
  )

  const sendMessage = useCallback(
    (text: string) => {
      const content = text.trim()
      if (!content || isStreaming) return

      const now = Date.now()
      const userMessage: ChatMessage = { id: createId(), role: 'user', parts: [{ type: 'text', text: content }], status: 'complete', createdAt: now }
      let conversationId = activeConversation?.id
      const history = [...(activeConversation?.messages ?? []), userMessage]

      if (conversationId) {
        setConversations((previous) =>
          previous.map((conversation) =>
            conversation.id === conversationId ? { ...conversation, updatedAt: now, messages: [...conversation.messages, userMessage] } : conversation,
          ),
        )
      } else {
        conversationId = createId()
        const conversation: Conversation = { id: conversationId, title: conversationTitle(content), messages: [userMessage], createdAt: now, updatedAt: now }
        setConversations((previous) => [conversation, ...previous])
        setActiveId(conversationId)
      }
      const needsTitle = !activeConversation?.titleGenerated
      const firstUserMessage = history.find((message) => message.role === 'user')
      void streamReply(conversationId, history, needsTitle && firstUserMessage ? messageText(firstUserMessage) : undefined)
    },
    [activeConversation, isStreaming, streamReply],
  )

  /** Drop the last failed or stopped reply and ask again with the same history. */
  const retryLast = useCallback(() => {
    if (!activeConversation || isStreaming) return
    const messages = activeConversation.messages
    const last = messages.at(-1)
    const history = last?.role === 'assistant' ? messages.slice(0, -1) : messages
    if (!history.length || !messageText(history.at(-1)!)) return

    setConversations((previous) => previous.map((conversation) => (conversation.id === activeConversation.id ? { ...conversation, messages: history } : conversation)))
    void streamReply(activeConversation.id, history)
  }, [activeConversation, isStreaming, streamReply])

  const stop = useCallback(() => abortRef.current?.abort(), [])

  const startNewChat = useCallback(() => {
    abortRef.current?.abort()
    setActiveId(null)
  }, [])

  const selectConversation = useCallback(
    (id: string) => {
      abortRef.current?.abort()
      setActiveId(id)
      // Chats from before titles were generated get one the first time they are opened.
      const conversation = conversations.find((candidate) => candidate.id === id)
      if (conversation && !conversation.titleGenerated) {
        const firstUser = conversation.messages.find((message) => message.role === 'user')
        const firstReply = conversation.messages.find((message) => message.role === 'assistant' && message.status === 'complete')
        if (firstUser) void requestTitle(id, messageText(firstUser), firstReply ? messageText(firstReply) : '')
      }
    },
    [conversations, requestTitle],
  )

  const deleteConversation = useCallback(
    (id: string) => {
      if (id === activeId) {
        abortRef.current?.abort()
        setActiveId(null)
      }
      setConversations((previous) => previous.filter((conversation) => conversation.id !== id))
    },
    [activeId],
  )

  return {
    conversations,
    activeConversation,
    isStreaming,
    sendMessage,
    retryLast,
    stop,
    startNewChat,
    selectConversation,
    deleteConversation,
  }
}
