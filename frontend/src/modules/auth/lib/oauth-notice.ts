/** Query parameters the backend adds when an OAuth redirect returns to the app. */
const PARAMS = ['auth_error', 'connection_error', 'connected'] as const

export interface OAuthNotice {
  tone: 'error' | 'success'
  message: string
}

const AUTH_ERRORS: Record<string, string> = {
  google_not_configured: 'Google sign-in isn’t set up yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env and restart the backend.',
  google_cancelled: 'Sign-in was cancelled.',
  email_not_allowed: 'This Google account isn’t allowed to use this Setu.',
  email_not_verified: 'Your Google email address isn’t verified.',
  state_mismatch: 'The sign-in attempt expired. Please try again.',
  provider_unreachable: 'Couldn’t reach Google. Check your connection and try again.',
}

const CONNECTION_ERRORS: Record<string, string> = {
  github_not_configured: 'GitHub isn’t set up yet. Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to backend/.env and restart the backend.',
  github_cancelled: 'GitHub connection was cancelled.',
  state_mismatch: 'The connection attempt expired. Please try again.',
  provider_unreachable: 'Couldn’t reach GitHub. Check your connection and try again.',
}

/** Read and strip the OAuth result from the URL so a refresh doesn't show it again. */
export function takeOAuthNotice(): OAuthNotice | null {
  const url = new URL(window.location.href)
  const [authError, connectionError, connected] = PARAMS.map((name) => url.searchParams.get(name))
  if (!authError && !connectionError && !connected) return null

  PARAMS.forEach((name) => url.searchParams.delete(name))
  window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)

  if (authError) return { tone: 'error', message: AUTH_ERRORS[authError] ?? 'Sign-in failed. Please try again.' }
  if (connectionError) return { tone: 'error', message: CONNECTION_ERRORS[connectionError] ?? 'Couldn’t connect GitHub. Please try again.' }
  return { tone: 'success', message: connected === 'github' ? 'GitHub connected.' : 'Account connected.' }
}
