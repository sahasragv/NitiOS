import { useState } from 'react'
import { CheckCircle2, FolderGit2, LogOut, MessageSquare, Plus, Search, Trash2, TriangleAlert, Unplug, X } from 'lucide-react'

import { SetuLogo } from '@/components/common/setu-logo'
import { cn } from '@/lib/utils'
import { startGitHubConnection, useConnections, useDisconnectGitHub, useSignOut } from '@/modules/auth/api/auth-api'
import type { OAuthNotice } from '@/modules/auth/lib/oauth-notice'
import type { User } from '@/modules/auth/types'
import { useTools } from '@/modules/chat/api/use-tools'
import { serverLabel, splitToolName } from '@/modules/chat/lib/tool-labels'
import type { Conversation } from '@/modules/chat/types'

export interface ChatSidebarProps {
  user: User
  /** Result of an OAuth redirect (e.g. "GitHub connected"), shown once. */
  notice: OAuthNotice | null
  conversations: Conversation[]
  activeId: string | null
  open: boolean
  onClose: () => void
  onNewChat: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

const DAY_MS = 24 * 60 * 60 * 1000

function groupByRecency(conversations: Conversation[]): { label: string; items: Conversation[] }[] {
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  const groups = [
    { label: 'Today', items: [] as Conversation[] },
    { label: 'Previous 7 days', items: [] as Conversation[] },
    { label: 'Older', items: [] as Conversation[] },
  ]
  for (const conversation of [...conversations].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const group = conversation.updatedAt >= startOfToday ? 0 : conversation.updatedAt >= startOfToday - 7 * DAY_MS ? 1 : 2
    groups[group].items.push(conversation)
  }
  return groups.filter((group) => group.items.length > 0)
}

export function ChatSidebar({ user, notice, conversations, activeId, open, onClose, onNewChat, onSelect, onDelete }: ChatSidebarProps) {
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()
  const visible = normalizedQuery ? conversations.filter((conversation) => conversation.title.toLowerCase().includes(normalizedQuery)) : conversations

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-brand-950/20 backdrop-blur-[2px] lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 isolate flex w-72 flex-col border-r border-brand-100 bg-gradient-to-b from-brand-50 via-brand-50/70 to-white transition-transform lg:relative lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="setu-grass pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-72" aria-hidden="true" />
        <div className="flex h-16 items-center gap-2.5 px-4">
          <SetuLogo className="size-9 rounded-xl" />
          <div className="leading-tight">
            <p className="text-base font-semibold tracking-tight text-slate-900">Setu</p>
            <p className="text-[11px] font-medium text-brand-700/70">One chat. All your apps.</p>
          </div>
          <button type="button" onClick={onClose} className="ml-auto rounded-md p-1.5 text-slate-500 hover:bg-brand-100 lg:hidden" aria-label="Close sidebar">
            <X className="size-4" />
          </button>
        </div>

        <div className="space-y-3 px-3 pt-1">
          <button
            type="button"
            onClick={onNewChat}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 px-3 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-500/25 transition hover:from-brand-600 hover:to-brand-700"
          >
            <Plus className="size-4" strokeWidth={2.5} /> New chat
          </button>
          <label className="flex items-center gap-2 rounded-xl border border-brand-100 bg-white/80 px-3 py-2 text-sm focus-within:border-brand-300 focus-within:ring-2 focus-within:ring-brand-100">
            <Search className="size-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search chats"
              aria-label="Search chats"
              className="w-full bg-transparent text-slate-700 placeholder:text-slate-400 focus:outline-none"
            />
          </label>
        </div>

        <nav className="mt-4 flex-1 overflow-y-auto px-3 pb-4" aria-label="Conversations">
          {conversations.length === 0 && (
            <div className="mx-1 rounded-xl border border-dashed border-brand-200 px-4 py-6 text-center text-sm text-slate-500">
              <MessageSquare className="mx-auto mb-2 size-5 text-brand-400" />
              Your chats will appear here.
            </div>
          )}
          {conversations.length > 0 && visible.length === 0 && <p className="px-3 py-2 text-sm text-slate-400">No chats match “{query}”.</p>}
          {groupByRecency(visible).map((group) => (
            <div key={group.label} className="mb-4">
              <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-brand-800/50">{group.label}</p>
              <ul className="space-y-0.5">
                {group.items.map((conversation) => {
                  const active = conversation.id === activeId
                  return (
                    <li key={conversation.id} className="group relative">
                      <button
                        type="button"
                        onClick={() => onSelect(conversation.id)}
                        className={cn(
                          'relative flex w-full items-center gap-2 rounded-lg px-3 py-2 pr-9 text-left text-sm text-slate-600 transition-colors hover:bg-brand-100/60',
                          active && 'bg-white font-medium text-brand-900 shadow-sm ring-1 ring-brand-100',
                        )}
                      >
                        {active && <span className="absolute inset-y-2 left-0 w-1 rounded-full bg-brand-500" aria-hidden="true" />}
                        <span className="truncate">{conversation.title}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onDelete(conversation.id)}
                        className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-400 opacity-0 hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
                        aria-label={`Delete “${conversation.title}”`}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="space-y-2 p-3">
          <ConnectedApps notice={notice} />
          <AccountRow user={user} />
        </div>
      </aside>
    </>
  )
}

function LiveDot() {
  return (
    <span className="relative flex size-2">
      <span className="absolute inline-flex size-full animate-ping rounded-full bg-brand-400 opacity-60" />
      <span className="relative inline-flex size-2 rounded-full bg-brand-500" />
    </span>
  )
}

/** Built-in tool servers plus the accounts this user can connect. */
function ConnectedApps({ notice }: { notice: OAuthNotice | null }) {
  const { data: tools, isLoading, isError } = useTools()
  const { data: connections } = useConnections()
  const disconnect = useDisconnectGitHub()
  const [visibleNotice, setVisibleNotice] = useState(notice)

  const servers = new Map<string, number>()
  for (const tool of tools ?? []) {
    const { server } = splitToolName(tool.name)
    if (server !== 'github') servers.set(server, (servers.get(server) ?? 0) + 1)
  }
  const github = connections?.find((connection) => connection.provider === 'github')

  return (
    <div className="rounded-xl border border-brand-100 bg-white/90 p-3 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-800/50">Connected apps</p>
      {visibleNotice && (
        <p
          className={cn(
            'mt-2 flex items-start gap-1.5 rounded-lg px-2 py-1.5 text-xs',
            visibleNotice.tone === 'success' ? 'bg-brand-50 text-brand-800' : 'bg-red-50 text-red-700',
          )}
          role="status"
        >
          {visibleNotice.tone === 'success' ? <CheckCircle2 className="mt-px size-3.5 shrink-0" /> : <TriangleAlert className="mt-px size-3.5 shrink-0" />}
          <span className="flex-1">{visibleNotice.message}</span>
          <button type="button" onClick={() => setVisibleNotice(null)} className="opacity-60 hover:opacity-100" aria-label="Dismiss">
            <X className="size-3.5" />
          </button>
        </p>
      )}
      <ul className="mt-2 space-y-1.5 text-sm">
        {isLoading && <li className="text-slate-400">Checking…</li>}
        {isError && (
          <li className="flex items-center gap-2 text-red-600">
            <span className="size-2 rounded-full bg-red-500" /> Backend offline
          </li>
        )}
        {[...servers].map(([server, count]) => (
          <li key={server} className="flex items-center gap-2 text-slate-700">
            <LiveDot />
            <span className="flex-1 truncate">{serverLabel(server)}</span>
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">{count} tools</span>
          </li>
        ))}
        {github && (
          <li className="flex items-center gap-2 text-slate-700">
            {github.connected ? <LiveDot /> : <FolderGit2 className="size-3.5 text-slate-400" />}
            <span className="min-w-0 flex-1 truncate">
              GitHub{github.connected && github.account && <span className="text-slate-400"> · @{github.account}</span>}
            </span>
            {github.connected ? (
              <button
                type="button"
                onClick={() => disconnect.mutate()}
                disabled={disconnect.isPending}
                className="rounded-md p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                aria-label="Disconnect GitHub"
                title="Disconnect GitHub"
              >
                <Unplug className="size-3.5" />
              </button>
            ) : (
              <button
                type="button"
                onClick={startGitHubConnection}
                disabled={!github.enabled}
                title={github.enabled ? undefined : 'Add GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET to backend/.env'}
                className="rounded-full bg-brand-600 px-2.5 py-0.5 text-[11px] font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                Connect
              </button>
            )}
          </li>
        )}
      </ul>
    </div>
  )
}

function AccountRow({ user }: { user: User }) {
  const signOut = useSignOut()
  const [imageFailed, setImageFailed] = useState(false)
  const initials = user.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className="flex items-center gap-2.5 rounded-xl px-2 py-1.5">
      {user.picture && !imageFailed ? (
        <img src={user.picture} alt="" referrerPolicy="no-referrer" onError={() => setImageFailed(true)} className="size-8 rounded-full ring-2 ring-white" />
      ) : (
        <span className="grid size-8 place-items-center rounded-full bg-brand-600 text-xs font-semibold text-white ring-2 ring-white">{initials}</span>
      )}
      <div className="min-w-0 flex-1 leading-tight">
        <p className="truncate text-sm font-medium text-slate-800">{user.name}</p>
        <p className="truncate text-xs text-slate-500">{user.email}</p>
      </div>
      <button
        type="button"
        onClick={() => signOut.mutate()}
        disabled={signOut.isPending}
        className="rounded-lg p-2 text-slate-500 hover:bg-white hover:text-slate-800 disabled:opacity-50"
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut className="size-4" />
      </button>
    </div>
  )
}
