import type { PropsWithChildren } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { apiQueryFn, type ApiQueryKey } from '@/services/api/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      queryFn: (context) => apiQueryFn({ ...context, queryKey: context.queryKey as ApiQueryKey }),
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})
export function AppProviders({ children }: PropsWithChildren) { return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider> }
