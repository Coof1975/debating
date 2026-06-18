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
      <div className="mb-6 flex flex-col gap-4 sm:mb-8 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="page-title">Personas</h1>
          <p className="page-subtitle">Manage debate participants and their system prompts.</p>
        </div>
        <Link to="/admin/personas/new" className="btn-primary w-full sm:w-auto">
          Add persona
        </Link>
      </div>

      <label className="mb-6 flex min-h-10 items-center gap-2 text-sm text-slate-400">
        <input
          type="checkbox"
          checked={showInactive}
          onChange={(e) => setShowInactive(e.target.checked)}
          className="h-4 w-4 rounded border-slate-600"
        />
        Show inactive personas
      </label>

      {loading && <p className="text-slate-400">Loading…</p>}
      {error && (
        <p className="mb-4 rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {error}
        </p>
      )}

      {!loading && personas.length === 0 && (
        <div className="card-padded border-dashed p-8 text-center text-slate-400 sm:p-10">
          No personas found.
        </div>
      )}

      <div className="grid gap-3 sm:gap-4">
        {personas.map((persona) => (
          <div
            key={persona.role}
            className="card-padded flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 sm:gap-3">
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
                className="btn-secondary min-h-9 px-3 py-2 text-sm"
              >
                Edit
              </Link>
              {persona.is_active && (
                <button
                  type="button"
                  onClick={() => handleDelete(persona.role)}
                  disabled={deleting === persona.role}
                  className="btn-danger min-h-9 px-3 py-2 text-sm"
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
