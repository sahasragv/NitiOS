import type { LucideIcon } from 'lucide-react'
import { Calculator, Clock, CloudSun, Coins, FolderGit2, Languages, Ruler, Wrench } from 'lucide-react'

import type { ToolCallStatus } from '@/modules/chat/types'

interface ToolPresentation {
  icon: LucideIcon
  short: string
  running: string
  done: string
}

/** Friendly wording for known tools; unknown tools fall back to their server and tool names. */
const KNOWN_TOOLS: Record<string, ToolPresentation> = {
  basics__calculator: { short: 'Calculator', icon: Calculator, running: 'Calculating', done: 'Calculated' },
  basics__current_time: { short: 'World clock', icon: Clock, running: 'Checking the time', done: 'Checked the time' },
  basics__convert_time: { short: 'Time zones', icon: Clock, running: 'Converting time zones', done: 'Converted time zones' },
  basics__get_weather: { short: 'Weather', icon: CloudSun, running: 'Checking the weather', done: 'Checked the weather' },
  basics__translate: { short: 'Translation', icon: Languages, running: 'Translating', done: 'Translated' },
  basics__convert_units: { short: 'Unit converter', icon: Ruler, running: 'Converting units', done: 'Converted units' },
  basics__convert_currency: { short: 'Currency', icon: Coins, running: 'Checking exchange rates', done: 'Converted currency' },
}

const SERVER_LABELS: Record<string, string> = { basics: 'Everyday tools', github: 'GitHub' }

export function splitToolName(name: string): { server: string; tool: string } {
  const [server, ...rest] = name.split('__')
  return rest.length ? { server, tool: rest.join('__') } : { server: '', tool: name }
}

export function serverLabel(server: string): string {
  return SERVER_LABELS[server] ?? server.charAt(0).toUpperCase() + server.slice(1)
}

export function toolPresentation(name: string, status: ToolCallStatus): { icon: LucideIcon; label: string } {
  const known = KNOWN_TOOLS[name]
  if (known) return { icon: known.icon, label: status === 'running' ? `${known.running}…` : known.done }

  const { server, tool } = splitToolName(name)
  const readable = tool.replace(/_/g, ' ')
  const icon = server === 'github' ? FolderGit2 : Wrench
  const prefix = server ? `${serverLabel(server)} · ` : ''
  return { icon, label: status === 'running' ? `${prefix}${readable}…` : `${prefix}${readable}` }
}

/** A short noun for a tool, used where tools are listed rather than reported as actions. */
export function toolShortLabel(name: string): { icon: LucideIcon; label: string } {
  const known = KNOWN_TOOLS[name]
  if (known) return { icon: known.icon, label: known.short }
  const { server, tool } = splitToolName(name)
  return { icon: server === 'github' ? FolderGit2 : Wrench, label: tool.replace(/_/g, ' ') }
}
