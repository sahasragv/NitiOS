import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
export interface LoadingSpinnerProps { label?: string; className?: string }
export function LoadingSpinner({ label = 'Loading', className }: LoadingSpinnerProps) { return <span className={cn('inline-flex items-center gap-2 text-sm text-slate-600', className)} role="status"><LoaderCircle className="size-4 animate-spin" aria-hidden="true" /><span>{label}</span></span> }
