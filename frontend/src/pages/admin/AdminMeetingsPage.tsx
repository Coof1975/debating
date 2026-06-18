import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { AdminLayout } from '../../components/AdminLayout'
import { ParticipantChips } from '../../components/meeting/ParticipantChips'
import { formatDate, statusClasses, statusLabel } from '../../lib/utils'
import type { MeetingListItem } from '../../types'

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'running', label: 'Running' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

export function AdminMeetingsPage() {
  const [meetings, setMeetings] = useState<MeetingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')

  const loadMeetings = useCallback(() => {
    setLoading(true)
    api
      .listMeetings({
        status: statusFilter || undefined,
        q: search.trim() || undefined,
        limit: 200,
      })
      .then(setMeetings)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [statusFilter, search])

  useEffect(() => {
    const timer = window.setTimeout(loadMeetings, search ? 300 : 0)
    return () => window.clearTimeout(timer)
  }, [loadMeetings, search])

  const summary = useMemo(
    () => ({
      total: meetings.length,
      pending: meetings.filter((m) => m.status === 'pending').length,
      completed: meetings.filter((m) => m.status === 'completed').length,
    }),
    [meetings],
  )

  async function handleDelete(id: string, topic: string) {
    if (!window.confirm(`Delete meeting "${topic}" permanently?`)) {
      return
    }
    setDeletingId(id)
    setError(null)
    try {
      await api.deleteMeeting(id)
      setMeetings((prev) => prev.filter((m) => m.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <AdminLayout>
      <div className="mb-6 sm:mb-8">
        <h1 className="page-title">All meetings</h1>
        <p className="page-subtitle">
          Manage every meeting in the system. Open a meeting in Workspace to run simulations or
          chat.
        </p>
        {!loading && (
          <p className="mt-2 text-xs text-slate-500">
            Showing {summary.total} · {summary.pending} pending · {summary.completed} completed
          </p>
        )}
      </div>

      <div className="mb-6 flex flex-col gap-3 sm:flex-row">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search topic…"
          className="input-field min-w-0 flex-1 text-sm"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input-field text-sm sm:max-w-xs"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="text-slate-400">Loading…</p>}
      {error && (
        <p className="mb-4 rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {error}
        </p>
      )}

      {!loading && meetings.length === 0 && (
        <div className="card-padded border-dashed p-8 text-center text-slate-400 sm:p-10">
          No meetings match your filters.
        </div>
      )}

      {!loading && meetings.length > 0 && (
        <>
          <div className="grid gap-3 lg:hidden">
            {meetings.map((meeting) => (
              <article key={meeting.id} className="card-padded">
                <div className="flex items-start justify-between gap-3">
                  <Link
                    to={`/meetings/${meeting.id}/overview`}
                    className="min-w-0 font-medium text-white hover:text-indigo-300"
                  >
                    {meeting.topic}
                  </Link>
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusClasses(meeting.status)}`}
                  >
                    {statusLabel(meeting.status)}
                  </span>
                </div>
                <div className="mt-3 space-y-2 text-xs text-slate-400">
                  {meeting.host_id && <p>Host: {meeting.host_id}</p>}
                  <ParticipantChips
                    participantIds={meeting.participant_ids}
                    hostId={meeting.host_id}
                  />
                  <p>
                    {meeting.scheduled_at
                      ? `Scheduled ${formatDate(meeting.scheduled_at)}`
                      : `Created ${formatDate(meeting.created_at)}`}
                  </p>
                </div>
                <div className="mt-4 flex gap-2">
                  <Link
                    to={`/meetings/${meeting.id}/overview`}
                    className="btn-secondary min-h-9 flex-1 px-3 py-2 text-xs"
                  >
                    Open
                  </Link>
                  <button
                    type="button"
                    onClick={() => handleDelete(meeting.id, meeting.topic)}
                    disabled={deletingId === meeting.id || meeting.status === 'running'}
                    className="btn-danger min-h-9 flex-1 px-3 py-2 text-xs"
                  >
                    {deletingId === meeting.id ? 'Deleting…' : 'Delete'}
                  </button>
                </div>
              </article>
            ))}
          </div>

          <div className="hidden overflow-x-auto rounded-xl border border-slate-800 lg:block">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="border-b border-slate-800 bg-slate-900/80 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Topic</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Host</th>
                  <th className="px-4 py-3 font-medium">Participants</th>
                  <th className="px-4 py-3 font-medium">Scheduled</th>
                  <th className="px-4 py-3 font-medium">Created</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {meetings.map((meeting) => (
                  <tr key={meeting.id} className="bg-slate-900/30 hover:bg-slate-900/50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/meetings/${meeting.id}/overview`}
                        className="font-medium text-white hover:text-indigo-300"
                      >
                        {meeting.topic}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusClasses(meeting.status)}`}
                      >
                        {statusLabel(meeting.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{meeting.host_id ?? '—'}</td>
                    <td className="px-4 py-3">
                      <ParticipantChips
                        participantIds={meeting.participant_ids}
                        hostId={meeting.host_id}
                      />
                    </td>
                    <td className="px-4 py-3 text-slate-400">
                      {meeting.scheduled_at ? formatDate(meeting.scheduled_at) : '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{formatDate(meeting.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <Link
                          to={`/meetings/${meeting.id}/overview`}
                          className="btn-secondary min-h-8 px-2.5 py-1 text-xs"
                        >
                          Open
                        </Link>
                        <button
                          type="button"
                          onClick={() => handleDelete(meeting.id, meeting.topic)}
                          disabled={deletingId === meeting.id || meeting.status === 'running'}
                          className="btn-danger min-h-8 px-2.5 py-1 text-xs"
                        >
                          {deletingId === meeting.id ? 'Deleting…' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </AdminLayout>
  )
}
