import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { AdminLayout } from '../components/AdminLayout'
import { formatDate } from '../lib/utils'
import type { PersonaListItem } from '../types'

export function PersonasPage() {
  const [personas, setPersonas] = useState<PersonaListItem[]>([])
  const [showInactive, setShowInactive] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  function loadPersonas() {
    setLoading(true)
    api
      .listPersonas(!showInactive)
      .then(setPersonas)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadPersonas()
  }, [showInactive])

  async function handleDelete(role: string) {
    if (!window.confirm(`Deactivate persona "${role}"? It will no longer appear in new meetings.`)) {
      return
    }
    setDeleting(role)
    setError(null)
    try {
      await api.deletePersona(role)
      loadPersonas()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setDeleting(null)
    }
  }

  return (
    <AdminLayout>
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-white">Personas</h1>
          <p className="mt-1 text-slate-400">Manage debate participants and their system prompts.</p>
        </div>
        <Link
          to="/admin/personas/new"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Add persona
        </Link>
      </div>

      <label className="mb-6 flex items-center gap-2 text-sm text-slate-400">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)}
        />
        Show inactive personas
      </label>

      {loading && <p className="text-slate-400">Loading…</p>}
      {error && <p className="mb-4 text-rose-400">{error}</p>}

      {!loading && personas.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center text-slate-400">
          No personas found.
        </div>
      )}

      <div className="grid gap-4">
        {personas.map((persona) => (
          <div
            key={persona.role}
            className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/50 p-5"
          >
            <div>
              <div className="flex items-center gap-3">
                <h2 className="font-medium text-white">{persona.role}</h2>
                {!persona.is_active && (
                  <span className="rounded-full bg-slate-700 px-2 py-0.5 text-xs text-slate-300">
                    Inactive
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-slate-400">{persona.display_title}</p>
              {persona.name && <p className="text-xs text-slate-500">{persona.name}</p>}
              <p className="mt-2 text-xs text-slate-500">Updated {formatDate(persona.updated_at)}</p>
            </div>
            <div className="flex gap-2">
              <Link
                to={`/admin/personas/${encodeURIComponent(persona.role)}`}
                className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
              >
                Edit
              </Link>
              {persona.is_active && (
                <button
                  type="button"
                  onClick={() => handleDelete(persona.role)}
                  disabled={deleting === persona.role}
                  className="rounded-lg border border-rose-500/40 px-3 py-1.5 text-sm text-rose-300 hover:bg-rose-950/40 disabled:opacity-50"
                >
                  {deleting === persona.role ? 'Deactivating…' : 'Deactivate'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </AdminLayout>
  )
}
