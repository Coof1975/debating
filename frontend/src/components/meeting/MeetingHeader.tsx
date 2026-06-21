import { Link } from 'react-router-dom'
import { formatDate, statusClasses, statusLabel } from '../../lib/utils'
import type { Meeting } from '../../types'
import { MeetingIdBadge } from './MeetingIdBadge'

type MeetingHeaderProps = {
  meeting: Meeting
  onDelete?: () => void
  deleting?: boolean
  showDelete?: boolean
}

export function MeetingHeader({
  meeting,
  onDelete,
  deleting,
  showDelete = true,
}: MeetingHeaderProps) {
  return (
    <div className="mb-5 flex flex-col gap-4 sm:mb-6 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0">
        <Link
          to="/"
          className="inline-flex min-h-9 items-center text-sm text-slate-500 hover:text-slate-300"
        >
          ← All meetings
        </Link>
        <h1 className="page-title mt-2 break-words">{meeting.topic}</h1>
        <p className="page-subtitle">
          Created {formatDate(meeting.created_at)}
          {meeting.scheduled_at && <> · Scheduled {formatDate(meeting.scheduled_at)}</>}
        </p>
        <MeetingIdBadge id={meeting.id} className="mt-2" />
      </div>
      <div className="flex shrink-0 flex-wrap items-center gap-2 sm:gap-3">
        <span
          className={`rounded-full px-3 py-1.5 text-xs font-medium ring-1 ring-inset ${statusClasses(meeting.status)}`}
        >
          {statusLabel(meeting.status)}
        </span>
        {showDelete && meeting.status !== 'running' && onDelete && (
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="btn-danger min-h-9 px-3 py-2 text-xs sm:min-h-10 sm:text-sm"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        )}
      </div>
    </div>
  )
}
