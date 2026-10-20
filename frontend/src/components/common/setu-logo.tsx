import logo from '@/assets/logo.png'
import { cn } from '@/lib/utils'

export interface SetuLogoProps { className?: string }

/** An "S" that doubles as an arched bridge: Setu means "bridge". */
export function SetuLogo({ className }: SetuLogoProps) {
  return <img src={logo} alt="" aria-hidden="true" className={cn('size-8 shrink-0 rounded-lg object-cover shadow-sm', className)} />
}
