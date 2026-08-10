import type { ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
export interface ErrorStateProps { title?: string; description?: string; action?: ReactNode; className?: string }
export function ErrorState({ title = 'Something went wrong', description = 'Please try again or return later.', action, className }: ErrorStateProps) { return <section className={cn('rounded-lg border border-red-200 bg-red-50 p-5', className)} role="alert"><div className="flex gap-3"><AlertCircle className="mt-0.5 size-5 shrink-0 text-red-700" /><div><h2 className="text-sm font-medium text-red-950">{title}</h2><p className="mt-1 text-sm text-red-800">{description}</p>{action && <div className="mt-3">{action}</div>}</div></div></section> }
