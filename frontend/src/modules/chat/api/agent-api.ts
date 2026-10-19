import { useQuery } from '@tanstack/react-query'

import { apiClient, type ApiQueryKey } from '@/services/api/client'
import { API_ENDPOINTS } from '@/services/api/endpoints'
import type { AgentInfo } from '@/modules/chat/types'

/** Ask the model for a short title summarizing a conversation's opening exchange. */
export async function generateTitle(message: string, reply: string): Promise<string> {
  const response = await apiClient.post<{ data: { title: string } }>(API_ENDPOINTS.agentTitle, { message, reply: reply || null })
  return response.data.data.title
}

/** The active model and connected tool servers. */
export function useAgentInfo() {
  return useQuery({
    queryKey: [API_ENDPOINTS.agentInfo] as ApiQueryKey,
    select: (envelope: unknown) => (envelope as { data: AgentInfo }).data,
    staleTime: 60_000,
  })
}
