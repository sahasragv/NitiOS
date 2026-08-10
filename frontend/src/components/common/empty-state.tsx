import type { ReactNode } from 'react'
import { Inbox } from 'lucide-react'
import { cn } from '@/lib/utils'
export interface EmptyStateProps { title: string; description?: string; action?: ReactNode; icon?: ReactNode; className?: string }
export function EmptyState({ title, description, action, icon = <Inbox className="size-5" />, className }: EmptyStateProps) { return <section className={cn('flex min-h-56 flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white px-6 py-10 text-center', className)}><span className="mb-3 text-slate-400">{icon}</span><h2 className="text-sm font-medium text-slate-950">{title}</h2>{description && <p className="mt-1 max-w-sm text-sm text-slate-600">{description}</p>}{action && <div className="mt-4">{action}</div>}</section> }
