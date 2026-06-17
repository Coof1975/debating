import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { Meeting, PersonaListItem, UpdateMeetingPayload } from '../../types'

const inputClass =
  'w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white'

type MeetingEditFormProps = {
  meeting: Meeting
  onSaved: (meeting: Meeting) => void
}

function splitScheduled(iso: string | null): { date: string; time: string } {
  if (!iso) return { date: '', time: '' }
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return { date: '', time: '' }
  return {
    date: d.toISOString().slice(0, 10),
    time: d.toTimeString().slice(0, 5),
  }
}

function toScheduledIso(date: string, time: string): string | null {
  if (!date.trim()) return null
  const value = new Date(`${date}T${time || '09:00'}`)
  if (Number.isNaN(value.getTime())) return null
  return value.toISOString()
}

export function MeetingEditForm({ meeting, onSaved }: MeetingEditFormProps) {
  const initial = splitScheduled(meeting.scheduled_at)
  const [personas, setPersonas] = useState<PersonaListItem[]>([])
  const [topic, setTopic] = useState(meeting.topic)
  const [notes, setNotes] = useState(meeting.notes)
  const [openingMessage, setOpeningMessage] = useState(meeting.opening_message)
  const [scheduledDate, setScheduledDate] = useState(initial.date)
  const [scheduledTime, setScheduledTime] = useState(initial.time)
  const [selected, setSelected] = useState<string[]>(meeting.participant_ids)
  const [hostId, setHostId] = useState(meeting.host_id ?? meeting.participant_ids[0] ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  useEffect(() => {
    api.listPersonas().then(setPersonas)
  }, [])

  function togglePersona(role: string) {
    setSelected((prev) => {
      const next = prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]
      let nextHost = hostId
      if (!next.includes(nextHost)) {
        nextHost = next.includes('CEO') ? 'CEO' : (next[0] ?? '')
      }
      setHostId(nextHost)
      return next
    })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!topic.trim()) {
      setError('Chủ đề không được để trống.')
      return
    }
    if (selected.length === 0) {
      setError('Chọn ít nhất một persona.')
      return
    }
    if (!hostId || !selected.includes(hostId)) {
      setError('Chọn người chủ trì trong danh sách tham gia.')
      return
    }

    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const payload: UpdateMeetingPayload = {
        topic: topic.trim(),
        notes: notes.trim(),
        opening_message: openingMessage.trim(),
        scheduled_at: toScheduledIso(scheduledDate, scheduledTime),
        participant_ids: selected,
        host_id: hostId,
      }
      const updated = await api.updateMeeting(meeting.id, payload)
      onSaved(updated)
      setSuccess('Đã lưu thay đổi.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-6 border-t border-slate-800 pt-6">
      <h3 className="text-sm font-semibold text-indigo-200">Chỉnh sửa meeting (pending)</h3>

      <div className="space-y-2">
        <label className="block text-xs text-slate-500">Chủ đề</label>
        <input value={topic} onChange={(e) => setTopic(e.target.value)} className={inputClass} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="block text-xs text-slate-500">Ngày dự kiến</label>
          <input
            type="date"
            value={scheduledDate}
            onChange={(e) => setScheduledDate(e.target.value)}
            className={inputClass}
          />
        </div>
        <div className="space-y-2">
          <label className="block text-xs text-slate-500">Giờ dự kiến</label>
          <input
            type="time"
            value={scheduledTime}
            onChange={(e) => setScheduledTime(e.target.value)}
            className={inputClass}
          />
        </div>
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-slate-500">Ghi chú</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className={inputClass}
        />
      </div>

      <div className="space-y-2">
        <label className="block text-xs text-slate-500">Lời mở đầu</label>
        <textarea
          value={openingMessage}
          onChange={(e) => setOpeningMessage(e.target.value)}
          rows={2}
          className={inputClass}
        />
      </div>

      <div className="space-y-3">
        <label className="block text-xs text-slate-500">Persona tham gia</label>
        <div className="grid gap-2 sm:grid-cols-2">
          {personas.map((persona) => (
            <label
              key={persona.role}
              className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/50 p-3"
            >
              <input
                type="checkbox"
                checked={selected.includes(persona.role)}
                onChange={() => togglePersona(persona.role)}
              />
              <span className="text-sm text-white">{persona.role}</span>
            </label>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <label className="block text-xs text-slate-500">Chủ trì</label>
        <div className="flex flex-wrap gap-3">
          {selected.map((role) => (
            <label
              key={role}
              className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-700 px-3 py-2"
            >
              <input
                type="radio"
                name="edit-host"
                checked={hostId === role}
                onChange={() => setHostId(role)}
              />
              <span className="text-sm text-white">{role}</span>
            </label>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-rose-400">{error}</p>}
      {success && <p className="text-sm text-emerald-400">{success}</p>}

      <button
        type="submit"
        disabled={saving}
        className="rounded-lg border border-indigo-500/40 px-4 py-2 text-sm text-indigo-200 hover:bg-indigo-950/40 disabled:opacity-50"
      >
        {saving ? 'Đang lưu…' : 'Lưu thay đổi'}
      </button>
    </form>
  )
}
