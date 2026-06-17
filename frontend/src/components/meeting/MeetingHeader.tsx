import { Link } from 'react-router-dom'
import { formatDate, statusClasses, statusLabel } from '../../lib/utils'
import type { Meeting } from '../../types'

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
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <Link to="/" className="text-sm text-slate-500 hover:text-slate-300">
          ← All meetings
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-white">{meeting.topic}</h1>
        <p className="mt-1 text-sm text-slate-400">
          Created {formatDate(meeting.created_at)}
          {meeting.scheduled_at && <> · Scheduled {formatDate(meeting.scheduled_at)}</>}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${statusClasses(meeting.status)}`}
        >
          {statusLabel(meeting.status)}
        </span>
        {showDelete && meeting.status !== 'running' && onDelete && (
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="rounded-lg border border-rose-500/40 px-3 py-1.5 text-sm text-rose-300 hover:bg-rose-950/40 disabled:opacity-50"
          >
            {deleting ? 'Deleting…' : 'Delete'}
          </button>
        )}
      </div>
    </div>
  )
}
