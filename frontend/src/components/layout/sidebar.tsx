import type { ReactNode } from 'react'
import { Building2 } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface SidebarItem { label: string; href?: string; icon?: ReactNode; active?: boolean }
export interface SidebarProps { items?: SidebarItem[]; className?: string }

export function Sidebar({ items = [], className }: SidebarProps) {
  return <aside className={cn('fixed inset-y-0 hidden w-64 border-r border-slate-200 bg-white lg:block', className)}>
    <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-6"><span className="grid size-8 place-items-center rounded-md bg-slate-900 text-white"><Building2 size={18} /></span><span className="text-sm font-semibold tracking-tight">NitiOS</span></div>
    <nav className="space-y-1 px-3 py-5">{items.map((item) => <a key={item.label} href={item.href ?? '#'} className={cn('flex items-center gap-3 rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-50', item.active && 'bg-slate-100 font-medium text-slate-950')}>{item.icon}{item.label}</a>)}</nav>
  </aside>
}
