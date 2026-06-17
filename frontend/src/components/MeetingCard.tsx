import { Link } from 'react-router-dom'
import type { MeetingListItem } from '../types'
import { formatDate, statusClasses, statusLabel } from '../lib/utils'

type MeetingCardProps = {
  meeting: MeetingListItem
  onDelete?: (id: string) => void
  deleting?: boolean
}

export function MeetingCard({ meeting, onDelete, deleting }: MeetingCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 transition hover:border-slate-600 hover:bg-slate-900">
      <div className="flex items-start justify-between gap-4">
        <Link to={`/meetings/${meeting.id}`} className="min-w-0 flex-1">
          <h2 className="font-medium text-white">{meeting.topic}</h2>
          <p className="mt-1 text-xs text-slate-500">
            {meeting.participant_ids.join(' · ')}
            {meeting.host_id && <> · Host {meeting.host_id}</>}
          </p>
        </Link>
        <div className="flex shrink-0 items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${statusClasses(meeting.status)}`}
          >
            {statusLabel(meeting.status)}
          </span>
          {onDelete && meeting.status !== 'running' && (
            <button
              type="button"
              onClick={() => onDelete(meeting.id)}
              disabled={deleting}
              className="rounded-lg border border-rose-500/40 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950/40 disabled:opacity-50"
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          )}
        </div>
      </div>
      <Link to={`/meetings/${meeting.id}`} className="mt-4 block">
        <div className="flex gap-4 text-xs text-slate-400">
          <span>Created {formatDate(meeting.created_at)}</span>
          {meeting.scheduled_at && <span>Scheduled {formatDate(meeting.scheduled_at)}</span>}
          {meeting.completed_at && <span>Completed {formatDate(meeting.completed_at)}</span>}
          {meeting.termination_reason && <span>Ended: {meeting.termination_reason}</span>}
        </div>
      </Link>
    </div>
  )
}
