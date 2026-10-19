export type ToolCallStatus = 'running' | 'success' | 'error'

export interface TextPart {
  type: 'text'
  text: string
}

export interface ToolCallPart {
  type: 'tool'
  id: string
  name: string
  arguments: Record<string, unknown>
  status: ToolCallStatus
  output?: string
}

/** Assistant replies interleave text and tool calls in the order they happened. */
export type MessagePart = TextPart | ToolCallPart

export type MessageStatus = 'streaming' | 'complete' | 'stopped' | 'error'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  parts: MessagePart[]
  status: MessageStatus
  error?: string
  createdAt: number
}

export interface Conversation {
  id: string
  title: string
  /** True once the model has summarized the conversation into a short title. */
  titleGenerated?: boolean
  messages: ChatMessage[]
  createdAt: number
  updatedAt: number
}

/** A prior message as the backend accepts it. */
export interface ChatHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

/** Server-Sent Events emitted by `POST /api/v1/agent/chat/stream`. */
export type ChatStreamEvent =
  | { type: 'text_delta'; text: string }
  | { type: 'tool_started'; id: string; name: string; arguments: Record<string, unknown> }
  | { type: 'tool_finished'; id: string; name: string; output: string; is_error: boolean }
  | { type: 'completed'; result: { content: string | null; steps: number; request_id: string } }
  | { type: 'error'; code: string; message: string }

export interface ToolDefinition {
  name: string
  description: string | null
  input_schema: Record<string, unknown>
}

export interface AgentInfo {
  provider: string
  model: string
  tool_count: number
  servers: string[]
}
