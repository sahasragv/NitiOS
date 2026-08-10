import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
export interface PageHeaderProps { title: string; description?: string; actions?: ReactNode; className?: string }
export function PageHeader({ title, description, actions, className }: PageHeaderProps) { return <div className={cn('flex flex-col gap-4 border-b border-slate-200 pb-5 sm:flex-row sm:items-start sm:justify-between', className)}><div><h1 className="text-2xl font-semibold tracking-tight text-slate-950">{title}</h1>{description && <p className="mt-1 text-sm text-slate-600">{description}</p>}</div>{actions && <div className="flex items-center gap-2">{actions}</div>}</div> }
