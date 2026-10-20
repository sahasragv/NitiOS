import { useState } from 'react'
import { ArrowUpRight, Calculator, ChevronLeft, ChevronRight, Clock, CloudSun, Coins, Languages, Ruler, Sparkles, type LucideIcon } from 'lucide-react'

import { SetuLogo } from '@/components/common/setu-logo'
import { cn } from '@/lib/utils'
import { useTools } from '@/modules/chat/api/use-tools'
import { toolShortLabel } from '@/modules/chat/lib/tool-labels'

interface Suggestion { icon: LucideIcon; title: string; prompt: string; tint: string }

const SUGGESTIONS: Suggestion[] = [
  { icon: CloudSun, title: 'Check the weather', prompt: 'What’s the weather in Hyderabad today?', tint: 'bg-sky-50 text-sky-600 ring-sky-100' },
  { icon: Clock, title: 'Plan across time zones', prompt: 'If it’s 9:30 AM in New York, what time is it in London and Tokyo?', tint: 'bg-amber-50 text-amber-600 ring-amber-100' },
  { icon: Coins, title: 'Convert currency', prompt: 'How much is 250 US dollars in Indian rupees today?', tint: 'bg-brand-50 text-brand-600 ring-brand-100' },
  { icon: Ruler, title: 'Convert units', prompt: 'Convert 42 km to miles and 30 °C to Fahrenheit.', tint: 'bg-teal-50 text-teal-600 ring-teal-100' },
  { icon: Calculator, title: 'Do the math', prompt: 'What is 18% GST on ₹24,500, and what’s the total?', tint: 'bg-violet-50 text-violet-600 ring-violet-100' },
  { icon: Languages, title: 'Translate', prompt: 'Translate “Thank you for your help” into Japanese and French.', tint: 'bg-rose-50 text-rose-600 ring-rose-100' },
]

/** Suggestions shown at once; the rest are a page away. */
const PAGE_SIZE = 3
const PAGE_COUNT = Math.ceil(SUGGESTIONS.length / PAGE_SIZE)

function greeting(hour: number): string {
  if (hour < 5) return 'Working late'
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

export interface ChatWelcomeProps { onSelect: (prompt: string) => void }

export function ChatWelcome({ onSelect }: ChatWelcomeProps) {
  const { data: tools } = useTools()
  const [page, setPage] = useState(0)
  const visible = SUGGESTIONS.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE)
  const goTo = (next: number) => setPage((next + PAGE_COUNT) % PAGE_COUNT)

  return (
    // `m-auto` centres the content but, unlike `justify-center`, keeps its top reachable when it overflows.
    <div className="flex flex-1 overflow-y-auto px-4 py-8 short:py-4">
      <div className="m-auto flex w-full max-w-3xl flex-col items-center">
        <div className="relative">
          <div className="absolute inset-0 -z-10 scale-150 rounded-full bg-brand-300/40 blur-2xl" aria-hidden="true" />
          <SetuLogo className="size-14 rounded-2xl shadow-lg shadow-brand-500/30 short:size-11" />
        </div>
        <span className="mt-5 inline-flex items-center gap-1.5 rounded-full border border-brand-200 bg-white/80 px-3 py-1 text-xs font-medium text-brand-700 shadow-sm short:mt-3">
          <Sparkles className="size-3.5" /> {greeting(new Date().getHours())}
        </span>
        <h1 className="mt-4 text-center text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl short:mt-2 short:text-3xl">
          How can I{' '}
          <span className="bg-gradient-to-r from-brand-600 via-brand-500 to-teal-500 bg-clip-text text-transparent">help you</span> today?
        </h1>
        <p className="mt-3 max-w-md text-center text-[15px] text-slate-500 short:mt-2 short:text-sm">
          Ask anything. Setu answers directly or reaches for the right app for weather, currencies, time zones and more.
        </p>

        {tools && tools.length > 0 && (
          <div className="mt-5 flex max-w-2xl flex-wrap justify-center gap-2 short:hidden">
            {tools.map((tool) => {
              const { icon: Icon, label } = toolShortLabel(tool.name)
              return (
                <span key={tool.name} className="inline-flex items-center gap-1.5 rounded-full border border-brand-100 bg-white/80 px-2.5 py-1 text-xs text-slate-600">
                  <Icon className="size-3.5 text-brand-600" /> {label}
                </span>
              )
            })}
          </div>
        )}

        <section className="mt-8 w-full short:mt-5" aria-label="Suggestions">
          <div className="mb-3 flex items-center justify-between px-1">
            <p className="text-xs font-semibold uppercase tracking-wider text-brand-800/50">Try asking</p>
            <div className="flex items-center gap-1">
              <button type="button" onClick={() => goTo(page - 1)} className="rounded-full p-1.5 text-slate-500 transition hover:bg-brand-100 hover:text-brand-700" aria-label="Previous suggestions">
                <ChevronLeft className="size-4" />
              </button>
              {Array.from({ length: PAGE_COUNT }, (_, index) => (
                <button
                  key={index}
                  type="button"
                  onClick={() => setPage(index)}
                  aria-label={`Suggestions page ${index + 1}`}
                  aria-current={index === page}
                  className={cn('h-1.5 rounded-full transition-all', index === page ? 'w-5 bg-brand-500' : 'w-1.5 bg-brand-200 hover:bg-brand-300')}
                />
              ))}
              <button type="button" onClick={() => goTo(page + 1)} className="rounded-full p-1.5 text-slate-500 transition hover:bg-brand-100 hover:text-brand-700" aria-label="More suggestions">
                <ChevronRight className="size-4" />
              </button>
            </div>
          </div>

          <div key={page} className="grid animate-fade-in gap-3 sm:grid-cols-3">
            {visible.map(({ icon: Icon, title, prompt, tint }) => (
              <button
                key={title}
                type="button"
                onClick={() => onSelect(prompt)}
                // Compact rows on phones, cards from `sm` up.
                className="group relative flex items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/90 p-3 pr-8 text-left shadow-sm backdrop-blur transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md hover:shadow-brand-500/10 sm:flex-col sm:items-start sm:gap-0 sm:p-4 short:sm:p-3"
              >
                <span className={cn('grid size-9 shrink-0 place-items-center rounded-xl ring-1 short:size-8', tint)}>
                  <Icon className="size-[18px]" />
                </span>
                <ArrowUpRight className="absolute right-3 top-3 size-4 text-slate-300 transition-colors group-hover:text-brand-500" />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-slate-900 sm:mt-3 short:sm:mt-2">{title}</span>
                  <span className="mt-0.5 line-clamp-1 text-[13px] leading-5 text-slate-500 sm:mt-1 sm:line-clamp-2">{prompt}</span>
                </span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
