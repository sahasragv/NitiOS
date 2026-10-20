import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiBaseURL, apiClient, type ApiError, type ApiQueryKey } from '@/services/api/client'
import { API_ENDPOINTS } from '@/services/api/endpoints'
import type { AccountConnection, AuthConfig, User } from '@/modules/auth/types'

export const CURRENT_USER_KEY = [API_ENDPOINTS.authMe] as ApiQueryKey
const CONNECTIONS_KEY = [API_ENDPOINTS.connections] as ApiQueryKey

/** The signed-in user, or `null` when there is no valid session. */
export function useCurrentUser() {
  return useQuery({
    queryKey: CURRENT_USER_KEY,
    queryFn: async (): Promise<User | null> => {
      try {
        const response = await apiClient.get<{ data: User }>(API_ENDPOINTS.authMe)
        return response.data.data
      } catch (error) {
        if ((error as ApiError).status === 401) return null
        throw error
      }
    },
    retry: false,
    staleTime: Infinity,
  })
}

/** Which providers the backend has credentials for. */
export function useAuthConfig() {
  return useQuery({
    queryKey: [API_ENDPOINTS.authConfig] as ApiQueryKey,
    select: (envelope: unknown) => (envelope as { data: AuthConfig }).data,
    staleTime: Infinity,
  })
}

export function useSignOut() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.post(API_ENDPOINTS.authLogout),
    onSettled: () => {
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== API_ENDPOINTS.authMe })
      queryClient.setQueryData(CURRENT_USER_KEY, null)
    },
  })
}

export function useConnections() {
  return useQuery({
    queryKey: CONNECTIONS_KEY,
    select: (envelope: unknown) => (envelope as { data: AccountConnection[] }).data,
    staleTime: 60_000,
  })
}

export function useDisconnectGitHub() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiClient.delete(API_ENDPOINTS.connectionGithub),
    onSettled: () => queryClient.invalidateQueries({ predicate: (query) => query.queryKey[0] !== API_ENDPOINTS.authMe }),
  })
}

/** OAuth flows are full-page redirects through the backend, not XHR calls. */
export function startGoogleSignIn(): void {
  window.location.assign(`${apiBaseURL}${API_ENDPOINTS.authGoogleLogin}`)
}

export function startGitHubConnection(): void {
  window.location.assign(`${apiBaseURL}${API_ENDPOINTS.connectionGithubLogin}`)
}
