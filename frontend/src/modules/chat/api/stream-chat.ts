import { apiBaseURL, notifyUnauthorized } from '@/services/api/client'
import { API_ENDPOINTS } from '@/services/api/endpoints'
import type { ChatHistoryMessage, ChatStreamEvent } from '@/modules/chat/types'

/**
 * Stream one chat turn. Uses `fetch` rather than axios or `EventSource` because
 * the request is a POST and the response body must be read incrementally.
 */
export async function streamChat(
  messages: ChatHistoryMessage[],
  onEvent: (event: ChatStreamEvent) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${apiBaseURL}${API_ENDPOINTS.agentChatStream}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ messages }),
    signal,
  })
  if (!response.ok || !response.body) throw new Error(await readErrorMessage(response))

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value.replace(/\r\n/g, '\n')
    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const data = buffer
        .slice(0, boundary)
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trimStart())
        .join('\n')
      buffer = buffer.slice(boundary + 2)
      if (data) onEvent(JSON.parse(data) as ChatStreamEvent)
      boundary = buffer.indexOf('\n\n')
    }
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  if (response.status === 401) {
    notifyUnauthorized()
    return 'Your session has ended. Please sign in again.'
  }
  if (response.status === 502 || response.status === 504) return 'Setu’s server is not reachable. Is the backend running?'
  try {
    const payload = (await response.json()) as { message?: string }
    return payload.message ?? `Request failed (${response.status}).`
  } catch {
    return `Request failed (${response.status}).`
  }
}
