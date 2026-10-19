/**
 * Central registry for API paths, relative to the API base URL (`/api` by default).
 */
export const API_ENDPOINTS = {
  agentChatStream: '/v1/agent/chat/stream',
  agentTools: '/v1/agent/tools',
  agentTitle: '/v1/agent/title',
  agentInfo: '/v1/agent/info',
} as const

export type ApiEndpoint = string
