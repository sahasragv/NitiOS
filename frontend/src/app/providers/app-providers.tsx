import type { PropsWithChildren } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { apiQueryFn, setUnauthorizedHandler, type ApiQueryKey } from '@/services/api/client'
import { CURRENT_USER_KEY } from '@/modules/auth/api/auth-api'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: (context) => apiQueryFn({ ...context, queryKey: context.queryKey as ApiQueryKey }),
      retry: (failureCount, error) => (error as { status?: number }).status !== 401 && failureCount < 1,
      refetchOnWindowFocus: false,
    },
  },
})

// Any 401 means the session ended: drop the user so the app shows the sign-in screen.
setUnauthorizedHandler(() => queryClient.setQueryData(CURRENT_USER_KEY, null))

export function AppProviders({ children }: PropsWithChildren) { return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider> }
