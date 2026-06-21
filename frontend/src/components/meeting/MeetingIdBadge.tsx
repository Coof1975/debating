import { useState } from 'react'

type MeetingIdBadgeProps = {
  id: string
  className?: string
}

export function MeetingIdBadge({ id, className = '' }: MeetingIdBadgeProps) {
  const [copied, setCopied] = useState(false)

  async function copyId() {
    try {
      await navigator.clipboard.writeText(id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Fallback for environments without clipboard API
      window.prompt('Meeting ID', id)
    }
  }

  return (
    <button
      type="button"
      onClick={() => void copyId()}
      className={`inline-flex max-w-full items-center gap-2 rounded-md bg-slate-800/60 px-2 py-1 font-mono text-xs text-slate-400 ring-1 ring-inset ring-slate-700 hover:text-slate-200 ${className}`}
      title="Click to copy meeting ID"
    >
      <span className="shrink-0 text-slate-500">ID</span>
      <span className="truncate">{id}</span>
      {copied && <span className="shrink-0 text-emerald-400">Copied</span>}
    </button>
  )
}
