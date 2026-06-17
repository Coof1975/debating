import { useState } from 'react'

type ChatComposerProps = {
  onSend: (content: string) => Promise<void>
  disabled?: boolean
  sending?: boolean
  placeholder?: string
}

export function ChatComposer({
  onSend,
  disabled = false,
  sending = false,
  placeholder = 'Nhập câu hỏi cho persona…',
}: ChatComposerProps) {
  const [text, setText] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const value = text.trim()
    if (!value || disabled || sending) return
    setText('')
    await onSend(value)
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 border-t border-slate-800 pt-4">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        disabled={disabled || sending}
        placeholder={placeholder}
        className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2.5 text-sm text-white disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || sending || !text.trim()}
        className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
      >
        {sending ? 'Đang gửi…' : 'Gửi'}
      </button>
    </form>
  )
}
