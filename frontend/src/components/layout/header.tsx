import type { ReactNode } from 'react'
import { Menu } from 'lucide-react'

import { cn } from '@/lib/utils'

export interface HeaderProps { children?: ReactNode; className?: string; onMenuClick?: () => void }

export function Header({ children, className, onMenuClick }: HeaderProps) {
  return <header className={cn('flex h-16 items-center border-b border-slate-200 bg-white px-5 lg:px-8', className)}>
    <button type="button" className="text-slate-600 lg:hidden" aria-label="Open navigation" onClick={onMenuClick}><Menu size={20} /></button>
    <div className="ml-auto flex items-center gap-4">{children}<div className="size-8 rounded-full bg-slate-200" aria-label="Profile placeholder" /></div>
  </header>
}
