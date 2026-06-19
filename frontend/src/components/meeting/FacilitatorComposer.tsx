import { useState } from 'react'

type FacilitatorComposerProps = {
  onSend: (content: string) => Promise<void>
  onEvaluate?: (content: string) => Promise<string | null>
  disabled?: boolean
  sending?: boolean
}

export function FacilitatorComposer({
  onSend,
  onEvaluate,
  disabled = false,
  sending = false,
}: FacilitatorComposerProps) {
  const [content, setContent] = useState('')
  const [hint, setHint] = useState<string | null>(null)
  const [evaluating, setEvaluating] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const text = content.trim()
    if (!text || disabled || sending) return
    setHint(null)
    await onSend(text)
    setContent('')
  }

  async function handleEvaluate() {
    const text = content.trim()
    if (!text || !onEvaluate || disabled || sending || evaluating) return
    setEvaluating(true)
    setHint(null)
    try {
      const message = await onEvaluate(text)
      setHint(message)
    } finally {
      setEvaluating(false)
    }
  }

  return (
    <div className="card-padded border border-amber-500/30 bg-amber-950/15">
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-amber-100">Bổ sung với vai trò người tổ chức</h2>
        <p className="mt-1 text-xs text-amber-200/70">
          Thêm ràng buộc, số liệu hoặc chỉ đạo mới — cả nhóm sẽ phản hồi nếu nội dung đủ ý nghĩa.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          disabled={disabled || sending}
          rows={4}
          placeholder="VD: Sếp vừa duyệt thêm 500 triệu ngân sách Q3. CFO và Marketing phản hồi tác động."
          className="input-field min-h-[6rem] resize-y disabled:opacity-50"
        />
        {hint && (
          <p className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-100/90">
            {hint}
          </p>
        )}
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
          <button
            type="submit"
            disabled={disabled || sending || !content.trim()}
            className="btn-primary w-full sm:w-auto"
          >
            {sending ? 'Đang gửi…' : 'Tiếp tục simulation'}
          </button>
          {onEvaluate && (
            <button
              type="button"
              onClick={handleEvaluate}
              disabled={disabled || sending || evaluating || !content.trim()}
              className="btn-secondary w-full sm:w-auto"
            >
              {evaluating ? 'Đang đánh giá…' : 'Xem trước đánh giá'}
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
