import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
export interface StatCardProps { label: string; value: ReactNode; description?: string; icon?: ReactNode; className?: string }
export function StatCard({ label, value, description, icon, className }: StatCardProps) { return <section className={cn('rounded-lg border border-slate-200 bg-white p-5', className)}><div className="flex items-start justify-between gap-4"><p className="text-sm font-medium text-slate-600">{label}</p>{icon && <span className="text-slate-500">{icon}</span>}</div><p className="mt-3 text-2xl font-semibold tracking-tight text-slate-950">{value}</p>{description && <p className="mt-1 text-sm text-slate-500">{description}</p>}</section> }
