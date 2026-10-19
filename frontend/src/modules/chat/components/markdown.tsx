import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { cn } from '@/lib/utils'

export interface MarkdownTextProps { text: string; className?: string }

/** Renders assistant Markdown. Raw HTML is not rendered, so model output cannot inject markup. */
export function MarkdownText({ text, className }: MarkdownTextProps) {
  return (
    <div
      className={cn(
        'prose prose-slate max-w-none prose-p:leading-7 prose-li:my-0.5 prose-pre:rounded-xl prose-pre:bg-slate-900 prose-code:before:content-none prose-code:after:content-none prose-a:text-brand-700 prose-strong:text-slate-900',
        className,
      )}
    >
      <Markdown remarkPlugins={[remarkGfm]} components={{ a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" /> }}>
        {text}
      </Markdown>
    </div>
  )
}
