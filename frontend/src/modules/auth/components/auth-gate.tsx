import type { ReactNode } from 'react'

import { LoadingSpinner } from '@/components/common/loading-spinner'
import { ErrorState } from '@/components/common/error-state'
import { useCurrentUser } from '@/modules/auth/api/auth-api'
import { takeOAuthNotice, type OAuthNotice } from '@/modules/auth/lib/oauth-notice'
import { LoginPage } from '@/modules/auth/pages/login-page'
import type { User } from '@/modules/auth/types'

// Read once at startup; reading inside a component would run twice under StrictMode and lose it.
const initialNotice = takeOAuthNotice()

interface AuthGateProps {
  children: (user: User, notice: OAuthNotice | null) => ReactNode
}

/** Render the app for a signed-in user, and the sign-in screen otherwise. */
export function AuthGate({ children }: AuthGateProps) {
  const { data: user, isPending, isError, refetch } = useCurrentUser()

  if (isPending) {
    return (
      <div className="setu-canvas grid h-dvh place-items-center">
        <LoadingSpinner label="Loading Setu" />
      </div>
    )
  }
  if (isError) {
    return (
      <div className="setu-canvas grid h-dvh place-items-center p-4">
        <ErrorState
          title="Setu’s server is not reachable"
          description="Make sure the backend is running, then try again."
          action={
            <button type="button" onClick={() => void refetch()} className="rounded-lg bg-white px-3 py-1.5 text-sm font-medium text-red-800 ring-1 ring-red-200 hover:bg-red-100">
              Try again
            </button>
          }
        />
      </div>
    )
  }
  if (!user) return <LoginPage notice={initialNotice?.tone === 'error' ? initialNotice : null} />
  return children(user, initialNotice)
}
