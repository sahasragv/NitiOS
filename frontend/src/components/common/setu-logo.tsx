import { cn } from '@/lib/utils'

export interface SetuLogoProps { className?: string }

/** A bridge arch with suspension cables: Setu means "bridge". */
export function SetuLogo({ className }: SetuLogoProps) {
  return (
    <span className={cn('grid size-8 shrink-0 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 text-white shadow-sm', className)}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="size-[62%]" aria-hidden="true">
        <path d="M3 17h18" />
        <path d="M4 17C6 9.5 18 9.5 20 17" />
        <path d="M8 12.6V17M12 11.3V17M16 12.6V17" strokeWidth="1.6" />
      </svg>
    </span>
  )
}
