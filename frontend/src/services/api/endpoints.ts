/**
 * Central registry for API paths, relative to the API base URL (`/api` by default).
 */
export const API_ENDPOINTS = {
  agentChatStream: '/v1/agent/chat/stream',
  agentTools: '/v1/agent/tools',
  agentTitle: '/v1/agent/title',
  agentInfo: '/v1/agent/info',
  authConfig: '/v1/auth/config',
  authMe: '/v1/auth/me',
  authLogout: '/v1/auth/logout',
  /** Browser navigation targets (full-page redirects), not XHR endpoints. */
  authGoogleLogin: '/v1/auth/google/login',
  connections: '/v1/connections',
  connectionGithubLogin: '/v1/connections/github/login',
  connectionGithub: '/v1/connections/github',
} as const

export type ApiEndpoint = string
