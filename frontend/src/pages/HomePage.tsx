import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { MeetingCard } from '../components/MeetingCard'
import type { MeetingListItem } from '../types'

export function HomePage() {
  const [meetings, setMeetings] = useState<MeetingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const loadMeetings = useCallback(() => {
    setLoading(true)
    api
      .listMeetings()
      .then(setMeetings)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    loadMeetings()
  }, [loadMeetings])

  async function handleDelete(id: string) {
    if (!window.confirm('Delete this meeting permanently? This cannot be undone.')) {
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
    <WorkspaceLayout>
      <div className="mb-6 sm:mb-8">
        <h1 className="page-title">Meeting history</h1>
        <p className="page-subtitle">
          View past simulations or start a new multi-persona debate.
        </p>
      </div>

      {loading && <p className="text-slate-400">Loading…</p>}
      {error && (
        <p className="mb-4 rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {error}
        </p>
      )}

      {!loading && meetings.length === 0 && (
        <div className="card-padded border-dashed p-8 text-center sm:p-10">
          <p className="text-slate-400">No meetings yet.</p>
          <Link
            to="/meetings/new"
            className="btn-primary mt-4 inline-flex"
          >
            Create your first meeting
          </Link>
        </div>
      )}

      <div className="grid gap-3 sm:gap-4">
        {meetings.map((meeting) => (
          <MeetingCard
            key={meeting.id}
            meeting={meeting}
            onDelete={handleDelete}
            deleting={deletingId === meeting.id}
          />
        ))}
      </div>
    </WorkspaceLayout>
  )
}
