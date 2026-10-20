export interface User {
  id: string
  email: string
  name: string
  picture: string | null
}

export interface AuthConfig {
  google_enabled: boolean
  github_enabled: boolean
}

export interface AccountConnection {
  provider: 'github'
  /** False when the server has no OAuth credentials for this provider. */
  enabled: boolean
  connected: boolean
  account: string | null
  connected_at: number | null
}
