import { settleInterruptedMessages } from '@/modules/chat/lib/messages'
import type { Conversation } from '@/modules/chat/types'

/**
 * Conversations live in the browser, one list per signed-in user, until the
 * backend stores them. Bump the key version if the stored shape changes incompatibly.
 */
const STORAGE_PREFIX = 'setu.conversations.v1'

function storageKey(userId: string): string {
  return `${STORAGE_PREFIX}.${userId}`
}

export function loadConversations(userId: string): Conversation[] {
  try {
    // Chats saved before sign-in existed are adopted by the first user who signs in on this browser.
    const stored = localStorage.getItem(storageKey(userId)) ?? localStorage.getItem(STORAGE_PREFIX)
    const parsed: unknown = stored ? JSON.parse(stored) : []
    return Array.isArray(parsed) ? (parsed as Conversation[]).map(settleInterruptedMessages) : []
  } catch {
    return []
  }
}

export function saveConversations(userId: string, conversations: Conversation[]): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(conversations))
    localStorage.removeItem(STORAGE_PREFIX)
  } catch {
    // Storage can be full or disabled; the session keeps working in memory.
  }
}
