import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { ArrowUp, Square, Wrench } from 'lucide-react'

import { cn } from '@/lib/utils'
import { useTools } from '@/modules/chat/api/use-tools'

export interface ChatComposerProps {
  isStreaming: boolean
  onSend: (text: string) => void
  onStop: () => void
  autoFocusKey?: string | null
}

const MAX_HEIGHT_PX = 200

export function ChatComposer({ isStreaming, onSend, onStop, autoFocusKey }: ChatComposerProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const canSend = value.trim().length > 0 && !isStreaming
  const { data: tools } = useTools()

  useEffect(() => {
    textareaRef.current?.focus()
  }, [autoFocusKey])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_HEIGHT_PX)}px`
  }, [value])

  const submit = (event?: FormEvent) => {
    event?.preventDefault()
    if (!canSend) return
    onSend(value)
    setValue('')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) submit(event)
  }

  return (
    <form onSubmit={submit} className="mx-auto w-full max-w-3xl px-4 pb-4 sm:px-6">
      <div className="rounded-3xl border border-brand-200 bg-white/95 p-2 shadow-lg shadow-brand-900/5 backdrop-blur transition focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-100">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Message Setu…"
          aria-label="Message Setu"
          className="block max-h-[200px] w-full resize-none bg-transparent px-3 py-2 text-[15px] leading-6 text-slate-900 placeholder:text-slate-400 focus:outline-none"
        />
        <div className="flex items-center gap-2 px-1">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
            <Wrench className="size-3.5" />
            {tools ? `${tools.length} tools ready` : 'Connecting tools…'}
          </span>
          <span className="ml-auto hidden text-xs text-slate-400 sm:inline">Enter to send · Shift + Enter for a new line</span>
        {isStreaming ? (
          <button type="button" onClick={onStop} className="grid size-9 shrink-0 place-items-center rounded-full bg-slate-900 text-white shadow-md hover:bg-slate-700 sm:ml-0" aria-label="Stop generating">
            <Square className="size-3.5 fill-current" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!canSend}
            className={cn('grid size-9 shrink-0 place-items-center rounded-full transition-colors', canSend ? 'bg-gradient-to-br from-brand-500 to-brand-600 text-white shadow-md shadow-brand-500/30 hover:from-brand-600 hover:to-brand-700' : 'bg-slate-100 text-slate-300')}
            aria-label="Send message"
          >
            <ArrowUp className="size-4" />
          </button>
        )}
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-slate-400">Setu can make mistakes. Check important information.</p>
    </form>
  )
}
