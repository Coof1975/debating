import { Link } from 'react-router-dom'
import type { MeetingListItem } from '../types'
import { formatDate, statusClasses, statusLabel } from '../lib/utils'
import { MeetingIdBadge } from './meeting/MeetingIdBadge'

type MeetingCardProps = {
  meeting: MeetingListItem
  onDelete?: (id: string) => void
  deleting?: boolean
}

export function MeetingCard({ meeting, onDelete, deleting }: MeetingCardProps) {
  return (
    <article className="card-padded transition hover:border-slate-600 hover:bg-slate-900 active:scale-[0.995]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <Link to={`/meetings/${meeting.id}`} className="min-w-0 flex-1">
          <h2 className="font-medium leading-snug text-white">{meeting.topic}</h2>
          <p className="mt-1.5 line-clamp-2 text-xs text-slate-500">
            {meeting.participant_ids.join(' · ')}
            {meeting.host_id && <> · Host {meeting.host_id}</>}
          </p>
        </Link>
        <div className="flex items-center justify-between gap-2 sm:shrink-0 sm:flex-col sm:items-end lg:flex-row lg:items-center">
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
              className="btn-danger min-h-9 px-2.5 py-1.5 text-xs"
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          )}
        </div>
      </div>
      <Link to={`/meetings/${meeting.id}`} className="mt-4 block">
        <div className="flex flex-col gap-2 text-xs text-slate-400 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-4 sm:gap-y-1">
          <MeetingIdBadge id={meeting.id} />
          <span>Created {formatDate(meeting.created_at)}</span>
          {meeting.scheduled_at && <span>Scheduled {formatDate(meeting.scheduled_at)}</span>}
          {meeting.completed_at && <span>Completed {formatDate(meeting.completed_at)}</span>}
          {meeting.termination_reason && <span>Ended: {meeting.termination_reason}</span>}
        </div>
      </Link>
    </article>
  )
}
