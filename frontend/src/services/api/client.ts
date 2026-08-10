import axios, { type AxiosError, type AxiosRequestConfig } from 'axios'
import type { QueryFunction } from '@tanstack/react-query'

/** Stable error shape exposed to UI and React Query consumers. */
export interface ApiError {
  message: string
  status: number | null
  code: string | null
  details: unknown
  requestId: string | null
}

export type ApiQueryKey = readonly [path: string, config?: AxiosRequestConfig]

const baseURL = import.meta.env.VITE_API_BASE_URL ?? import.meta.env.VITE_API_URL ?? '/api'

/** Shared HTTP client. Authentication, request IDs, and logging are added here when available. */
export const apiClient = axios.create({
  baseURL,
  headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use(
  (config) => {
    // Future extension points: attach JWT, token refresh metadata, request IDs, and telemetry.
    return config
  },
  (error: unknown) => Promise.reject(normalizeApiError(error)),
)

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(normalizeApiError(error)),
)

/** Converts Axios and network failures into the application-wide API error contract. */
export function normalizeApiError(error: unknown): ApiError {
  if (!axios.isAxiosError(error)) {
    return { message: 'An unexpected error occurred.', status: null, code: null, details: error, requestId: null }
  }

  const axiosError = error as AxiosError<{
    message?: string
    code?: string
    details?: unknown
    error?: { message?: string; code?: string; details?: unknown }
  }>
  const payload = axiosError.response?.data
  const nestedError = payload?.error

  return {
    message: nestedError?.message ?? payload?.message ?? axiosError.message ?? 'The request could not be completed.',
    status: axiosError.response?.status ?? null,
    code: nestedError?.code ?? payload?.code ?? axiosError.code ?? null,
    details: nestedError?.details ?? payload?.details ?? null,
    requestId: axiosError.response?.headers['x-request-id'] ?? null,
  }
}

/**
 * Default React Query transport. Use a query key of `[path, axiosConfig?]`.
 * Feature queries can override this when they need custom response handling.
 */
export const apiQueryFn: QueryFunction<unknown, ApiQueryKey> = async ({ queryKey }) => {
  const [path, config] = queryKey
  const response = await apiClient.get(path, config)
  return response.data
}
