import { useEffect, useState } from 'react'
import { Check, CircleAlert, Copy, RotateCcw } from 'lucide-react'

import { SetuLogo } from '@/components/common/setu-logo'
import { MarkdownText } from '@/modules/chat/components/markdown'
import { ToolCallChip } from '@/modules/chat/components/tool-call-chip'
import { messageText } from '@/modules/chat/lib/messages'
import type { ChatMessage as ChatMessageModel } from '@/modules/chat/types'

export interface ChatMessageProps {
  message: ChatMessageModel
  isLast: boolean
  onRetry: () => void
}

export function ChatMessage({ message, isLast, onRetry }: ChatMessageProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-3xl rounded-br-lg bg-gradient-to-br from-brand-100 to-brand-50 px-4 py-2.5 text-[15px] leading-7 text-slate-900 shadow-sm ring-1 ring-brand-200/60">
          {messageText(message)}
        </div>
      </div>
    )
  }

  const isStreaming = message.status === 'streaming'
  const lastPart = message.parts.at(-1)
  // Show the typing indicator until text arrives, including while a tool is about to start.
  const showTyping = isStreaming && (!lastPart || (lastPart.type === 'tool' && lastPart.status !== 'running'))

  return (
    <div className="group flex gap-3">
      <SetuLogo className="mt-0.5 size-8 rounded-xl shadow-sm shadow-brand-500/20" />
      <div className="min-w-0 flex-1">
        <p className="mb-1 text-xs font-semibold text-brand-800/70">Setu</p>
        {message.parts.map((part, index) =>
          part.type === 'text' ? (
            <MarkdownText key={index} text={part.text} className="text-[15px]" />
          ) : (
            <ToolCallChip key={part.id} part={part} />
          ),
        )}
        {showTyping && <TypingIndicator since={message.createdAt} />}

        {message.status === 'error' && (
          <div className="mt-2 flex flex-wrap items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            <CircleAlert className="size-4 shrink-0" />
            <span className="flex-1">{message.error ?? 'Something went wrong.'}</span>
            {isLast && (
              <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 font-medium hover:underline">
                <RotateCcw className="size-3.5" /> Retry
              </button>
            )}
          </div>
        )}

        {message.status === 'stopped' && (
          <div className="mt-1 flex items-center gap-3 text-xs text-slate-400">
            <span>Stopped</span>
            {isLast && (
              <button type="button" onClick={onRetry} className="inline-flex items-center gap-1 hover:text-slate-600">
                <RotateCcw className="size-3" /> Regenerate
              </button>
            )}
          </div>
        )}

        {message.status === 'complete' && <MessageActions text={messageText(message)} />}
      </div>
    </div>
  )
}

/** After this long without output, explain that local models can be slow. */
const SLOW_HINT_AFTER_SECONDS = 20

function TypingIndicator({ since }: { since: number }) {
  const [seconds, setSeconds] = useState(() => Math.floor((Date.now() - since) / 1000))

  useEffect(() => {
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - since) / 1000)), 1000)
    return () => window.clearInterval(timer)
  }, [since])

  return (
    <div className="mt-1" role="status">
      <div className="inline-flex items-center gap-2 rounded-full border border-brand-100 bg-brand-50/80 px-3 py-1.5 text-xs font-medium text-brand-700">
        Thinking
        <span className="flex items-center gap-1" aria-hidden="true">
          {[0, 150, 300].map((delay) => (
            <span key={delay} className="size-1.5 animate-typing-dot rounded-full bg-brand-500" style={{ animationDelay: `${delay}ms` }} />
          ))}
        </span>
        {seconds >= 3 && <span className="tabular-nums text-brand-600/70">{seconds}s</span>}
      </div>
      {seconds >= SLOW_HINT_AFTER_SECONDS && (
        <p className="mt-1.5 text-xs text-slate-400">Still working. Local models on a CPU can take a few minutes, especially for long or non-English answers.</p>
      )}
    </div>
  )
}

function MessageActions({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  if (!text) return null

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be denied; nothing useful to show.
    }
  }

  return (
    <div className="mt-1 flex opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
      <button type="button" onClick={copy} className="rounded-md p-1.5 text-slate-400 hover:bg-brand-50 hover:text-brand-700" aria-label="Copy reply">
        {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      </button>
    </div>
  )
}
