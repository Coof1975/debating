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
    if (!window.confirm(`Delete meeting "${topic}"? This cannot be undone.`)) {
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
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">All meetings</h1>
          <p className="mt-1 text-slate-400">
            Manage every meeting in the system. Open a meeting in Workspace to run simulations or
            chat.
          </p>
          {!loading && (
            <p className="mt-2 text-xs text-slate-500">
              Showing {summary.total} · {summary.pending} pending · {summary.completed} completed
            </p>
          )}
        </div>
      </div>

      <div className="mb-6 flex flex-wrap gap-3">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search topic…"
          className="min-w-[200px] flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value || 'all'} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      {loading && <p className="text-slate-400">Loading…</p>}
      {error && <p className="mb-4 text-rose-400">{error}</p>}

      {!loading && meetings.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center text-slate-400">
          No meetings match your filters.
        </div>
      )}

      {!loading && meetings.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-800">
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
                        className="rounded-lg border border-slate-600 px-2.5 py-1 text-xs text-slate-200 hover:bg-slate-800"
                      >
                        Open
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleDelete(meeting.id, meeting.topic)}
                        disabled={deletingId === meeting.id || meeting.status === 'running'}
                        className="rounded-lg border border-rose-500/40 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-950/40 disabled:opacity-50"
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
      )}
    </AdminLayout>
  )
}
