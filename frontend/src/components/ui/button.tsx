import type { ButtonHTMLAttributes } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'
const buttonVariants = cva('inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:pointer-events-none disabled:opacity-50', { variants: { variant: { default: 'bg-slate-900 text-white hover:bg-slate-800', outline: 'border border-slate-200 bg-white hover:bg-slate-50' }, size: { default: 'h-9 px-4', sm: 'h-8 px-3' } }, defaultVariants: { variant: 'default', size: 'default' } })
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}
export function Button({ className, variant, size, ...props }: ButtonProps) { return <button className={cn(buttonVariants({ variant, size }), className)} {...props} /> }
