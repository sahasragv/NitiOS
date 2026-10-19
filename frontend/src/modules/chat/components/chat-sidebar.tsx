import { useState } from 'react'
import { Cloud, Cpu, MessageSquare, Plus, Search, Trash2, X } from 'lucide-react'

import { SetuLogo } from '@/components/common/setu-logo'
import { cn } from '@/lib/utils'
import { useAgentInfo } from '@/modules/chat/api/agent-api'
import { useTools } from '@/modules/chat/api/use-tools'
import { serverLabel, splitToolName } from '@/modules/chat/lib/tool-labels'
import type { Conversation } from '@/modules/chat/types'

export interface ChatSidebarProps {
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

export function ChatSidebar({ conversations, activeId, open, onClose, onNewChat, onSelect, onDelete }: ChatSidebarProps) {
  const [query, setQuery] = useState('')
  const normalizedQuery = query.trim().toLowerCase()
  const visible = normalizedQuery ? conversations.filter((conversation) => conversation.title.toLowerCase().includes(normalizedQuery)) : conversations

  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-brand-950/20 backdrop-blur-[2px] lg:hidden" onClick={onClose} aria-hidden="true" />}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-brand-100 bg-gradient-to-b from-brand-50 via-brand-50/70 to-white transition-transform lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
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
          <ConnectedApps />
          <ModelCard />
        </div>
      </aside>
    </>
  )
}

/** Which MCP servers are connected, derived from the backend's tool list. */
function ConnectedApps() {
  const { data: tools, isLoading, isError } = useTools()
  const servers = new Map<string, number>()
  for (const tool of tools ?? []) {
    const { server } = splitToolName(tool.name)
    servers.set(server, (servers.get(server) ?? 0) + 1)
  }

  return (
    <div className="rounded-xl border border-brand-100 bg-white/90 p-3 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-brand-800/50">Connected apps</p>
      <ul className="mt-2 space-y-1.5 text-sm">
        {isLoading && <li className="text-slate-400">Checking…</li>}
        {isError && (
          <li className="flex items-center gap-2 text-red-600">
            <span className="size-2 rounded-full bg-red-500" /> Backend offline
          </li>
        )}
        {!isLoading && !isError && servers.size === 0 && <li className="text-slate-400">No apps connected</li>}
        {[...servers].map(([server, count]) => (
          <li key={server} className="flex items-center gap-2 text-slate-700">
            <span className="relative flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-brand-400 opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-brand-500" />
            </span>
            <span className="flex-1 truncate">{serverLabel(server)}</span>
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-medium text-brand-700">{count} tools</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ModelCard() {
  const { data: info } = useAgentInfo()
  if (!info) return null
  const isCloud = info.provider !== 'ollama'
  const Icon = isCloud ? Cloud : Cpu
  return (
    <div className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-xs text-slate-500">
      <span className="grid size-7 place-items-center rounded-lg bg-brand-100 text-brand-700">
        <Icon className="size-3.5" />
      </span>
      <div className="min-w-0 leading-tight">
        <p className="truncate font-medium text-slate-700">{info.model}</p>
        <p>{isCloud ? 'Cloud model' : 'Running locally'}</p>
      </div>
    </div>
  )
}
