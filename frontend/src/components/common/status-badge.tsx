import type { HTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
const statusBadgeVariants = cva('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', { variants: { status: { neutral: 'bg-slate-100 text-slate-700', success: 'bg-emerald-100 text-emerald-800', warning: 'bg-amber-100 text-amber-800', danger: 'bg-red-100 text-red-800', info: 'bg-blue-100 text-blue-800' } }, defaultVariants: { status: 'neutral' } })
export interface StatusBadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof statusBadgeVariants> {}
export function StatusBadge({ className, status, ...props }: StatusBadgeProps) { return <span className={cn(statusBadgeVariants({ status }), className)} {...props} /> }
