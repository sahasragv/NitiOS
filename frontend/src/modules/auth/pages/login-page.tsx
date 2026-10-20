import { AlertCircle, Info } from 'lucide-react'

import { SetuLogo } from '@/components/common/setu-logo'
import { startGoogleSignIn, useAuthConfig } from '@/modules/auth/api/auth-api'
import type { OAuthNotice } from '@/modules/auth/lib/oauth-notice'

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="size-5" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.5z" />
    </svg>
  )
}

export function LoginPage({ notice }: { notice: OAuthNotice | null }) {
  const { data: config } = useAuthConfig()
  const googleMissing = config && !config.google_enabled

  return (
    <main className="setu-canvas grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-sm animate-fade-in rounded-3xl border border-brand-100 bg-white/90 p-8 text-center shadow-xl shadow-brand-900/5 backdrop-blur">
        <SetuLogo className="mx-auto size-14 rounded-2xl shadow-lg shadow-brand-500/30" />
        <h1 className="mt-5 text-2xl font-bold tracking-tight text-slate-900">Welcome to Setu</h1>
        <p className="mt-1.5 text-sm text-slate-500">One chat. All your apps. Sign in to keep your chats and connected accounts private to you.</p>

        {notice && (
          <p className="mt-5 flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2.5 text-left text-sm text-red-700 ring-1 ring-red-100" role="alert">
            <AlertCircle className="mt-0.5 size-4 shrink-0" /> {notice.message}
          </p>
        )}

        <button
          type="button"
          onClick={startGoogleSignIn}
          disabled={googleMissing}
          className="mt-6 flex w-full items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-brand-300 hover:bg-brand-50/50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <GoogleMark /> Continue with Google
        </button>

        {googleMissing && (
          <p className="mt-4 flex items-start gap-2 rounded-xl bg-amber-50 px-3 py-2.5 text-left text-xs leading-5 text-amber-800 ring-1 ring-amber-100">
            <Info className="mt-0.5 size-4 shrink-0" />
            <span>
              Google sign-in isn’t set up yet. Add <code className="font-mono">GOOGLE_CLIENT_ID</code> and <code className="font-mono">GOOGLE_CLIENT_SECRET</code> to
              <code className="font-mono"> backend/.env</code>, then restart the backend.
            </span>
          </p>
        )}
      </div>
    </main>
  )
}
