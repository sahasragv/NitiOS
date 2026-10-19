import { useQuery } from '@tanstack/react-query'

import { API_ENDPOINTS } from '@/services/api/endpoints'
import type { ApiQueryKey } from '@/services/api/client'
import type { ToolDefinition } from '@/modules/chat/types'

interface ToolsEnvelope {
  data: ToolDefinition[]
}

/** Tools the assistant can use right now, as reported by the backend. */
export function useTools() {
  return useQuery({
    queryKey: [API_ENDPOINTS.agentTools] as ApiQueryKey,
    select: (envelope: unknown) => (envelope as ToolsEnvelope).data,
    staleTime: 60_000,
  })
}
