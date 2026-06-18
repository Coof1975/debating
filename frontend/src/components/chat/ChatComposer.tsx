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
    <form
      onSubmit={handleSubmit}
      className="sticky bottom-0 -mx-1 border-t border-slate-800 bg-slate-900/95 px-1 pt-3 backdrop-blur-sm sm:static sm:mx-0 sm:bg-transparent sm:px-0 sm:backdrop-blur-none"
      style={{ paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))' }}
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled || sending}
          placeholder={placeholder}
          className="input-field min-w-0 flex-1 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || sending || !text.trim()}
          className="btn-primary w-full shrink-0 sm:w-auto"
        >
          {sending ? 'Đang gửi…' : 'Gửi'}
        </button>
      </div>
    </form>
  )
}
