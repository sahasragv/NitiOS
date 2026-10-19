import { settleInterruptedMessages } from '@/modules/chat/lib/messages'
import type { Conversation } from '@/modules/chat/types'

/**
 * Conversations live in the browser until the backend stores them. Bump the
 * key version if the stored shape changes incompatibly.
 */
const STORAGE_KEY = 'setu.conversations.v1'

export function loadConversations(): Conversation[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    const parsed: unknown = stored ? JSON.parse(stored) : []
    return Array.isArray(parsed) ? (parsed as Conversation[]).map(settleInterruptedMessages) : []
  } catch {
    return []
  }
}

export function saveConversations(conversations: Conversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations))
  } catch {
    // Storage can be full or disabled; the session keeps working in memory.
  }
}
