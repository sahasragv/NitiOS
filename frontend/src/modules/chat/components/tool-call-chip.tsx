import { useState } from 'react'
import { ChevronDown, CircleAlert, LoaderCircle } from 'lucide-react'

import { cn } from '@/lib/utils'
import { toolPresentation } from '@/modules/chat/lib/tool-labels'
import type { ToolCallPart } from '@/modules/chat/types'

export interface ToolCallChipProps { part: ToolCallPart }

/** A compact record of one tool call; expands to show its inputs and output. */
export function ToolCallChip({ part }: ToolCallChipProps) {
  const [open, setOpen] = useState(false)
  const { icon: Icon, label } = toolPresentation(part.name, part.status)
  const isRunning = part.status === 'running'
  const isError = part.status === 'error'

  return (
    <div className="my-2">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        disabled={isRunning}
        aria-expanded={open}
        className={cn(
          'inline-flex max-w-full items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
          isError ? 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100' : 'border-brand-200 bg-brand-50 text-brand-800 hover:bg-brand-100',
          isRunning && 'cursor-default hover:bg-brand-50',
        )}
      >
        {isRunning ? <LoaderCircle className="size-3.5 animate-spin text-brand-600" /> : isError ? <CircleAlert className="size-3.5" /> : <Icon className="size-3.5 text-brand-600" />}
        <span className="truncate">{isError ? `${label} — failed` : label}</span>
        {!isRunning && <ChevronDown className={cn('size-3.5 shrink-0 transition-transform', open && 'rotate-180')} />}
      </button>
      {open && !isRunning && (
        <div className="mt-2 space-y-2 rounded-xl border border-brand-100 bg-brand-50/60 p-3 text-xs">
          <div>
            <p className="mb-1 font-medium text-slate-500">Tool</p>
            <code className="text-slate-700">{part.name}</code>
          </div>
          <div>
            <p className="mb-1 font-medium text-slate-500">Input</p>
            <pre className="overflow-x-auto whitespace-pre-wrap break-words text-slate-700">{JSON.stringify(part.arguments, null, 2)}</pre>
          </div>
          <div>
            <p className="mb-1 font-medium text-slate-500">Result</p>
            <pre className={cn('max-h-64 overflow-auto whitespace-pre-wrap break-words', isError ? 'text-red-700' : 'text-slate-700')}>{part.output}</pre>
          </div>
        </div>
      )}
    </div>
  )
}
