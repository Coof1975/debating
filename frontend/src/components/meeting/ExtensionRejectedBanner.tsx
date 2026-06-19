import { Link } from 'react-router-dom'
import { extensionSuggestionLabel } from '../../lib/meetingExtension'
import type { ExtensionRejectedDetail } from '../../types'

type ExtensionRejectedBannerProps = {
  meetingId: string
  rejection: ExtensionRejectedDetail
  pendingContent: string
  onForceContinue: () => void
  onDismiss: () => void
  forcing?: boolean
}

export function ExtensionRejectedBanner({
  meetingId,
  rejection,
  pendingContent,
  onForceContinue,
  onDismiss,
  forcing = false,
}: ExtensionRejectedBannerProps) {
  const showChatLink = rejection.suggestion === 'chat_with_persona'

  return (
    <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-sm">
      <p className="font-medium text-amber-100">Chưa mở lại simulation</p>
      <p className="mt-1 text-amber-200/90">{rejection.reason}</p>
      <p className="mt-2 text-xs text-amber-200/70">
        {extensionSuggestionLabel(rejection.suggestion)}
      </p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
        {showChatLink && (
          <Link
            to={`/meetings/${meetingId}/chat`}
            className="btn-secondary w-full text-center sm:w-auto"
          >
            Mở tab Chat
          </Link>
        )}
        {pendingContent.trim() && (
          <button
            type="button"
            onClick={onForceContinue}
            disabled={forcing}
            className="btn-primary w-full sm:w-auto"
          >
            {forcing ? 'Đang chạy…' : 'Vẫn tiếp tục'}
          </button>
        )}
        <button
          type="button"
          onClick={onDismiss}
          className="btn-secondary w-full sm:w-auto"
        >
          Đóng
        </button>
      </div>
    </div>
  )
}
