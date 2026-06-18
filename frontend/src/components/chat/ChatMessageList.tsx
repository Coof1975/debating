import type { ChatMessage } from '../../types'
import { roleColor } from '../../lib/utils'

type ChatMessageListProps = {
  messages: ChatMessage[]
  personaName: string
  personaId: string
  loading?: boolean
}

export function ChatMessageList({
  messages,
  personaName,
  personaId,
  loading,
}: ChatMessageListProps) {
  if (loading) {
    return <p className="text-sm text-slate-400">Đang tải lịch sử chat…</p>
  }

  if (messages.length === 0) {
    return (
      <div className="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-slate-700 p-8 text-center">
        <p className="text-sm text-slate-400">
          Bắt đầu hỏi {personaName || personaId} về nội dung cuộc họp.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {messages.map((message) => {
        const isUser = message.role === 'user'
        return (
          <div
            key={message.id}
            className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm sm:max-w-[85%] ${
                isUser
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-800 text-slate-100 ring-1 ring-slate-700'
              }`}
            >
              {!isUser && (
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold text-white ${roleColor(personaId)}`}
                  >
                    {personaId.slice(0, 1)}
                  </span>
                  <span className="text-xs font-medium text-slate-300">
                    {personaName || personaId}
                  </span>
                </div>
              )}
              <p className="whitespace-pre-wrap">{message.content}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
