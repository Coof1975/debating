import { useState } from 'react'
import { api } from '../../api/client'

export function AdminSeedPanel() {
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSeed(force: boolean) {
    if (!window.confirm(`${force ? 'Force re-seed' : 'Seed'} database from markdown files?`)) {
      return
    }
    setLoading(true)
    setMessage(null)
    setError(null)
    try {
      const result = await api.seedDatabase(force)
      const counts = Object.entries(result.counts)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', ')
      setMessage(`${result.status} — ${counts}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Seed failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mt-8 border-t border-slate-800 pt-6">
      <p className="px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Database
      </p>
      <div className="mt-2 space-y-2 px-3">
        <button
          type="button"
          disabled={loading}
          onClick={() => handleSeed(false)}
          className="block w-full rounded-lg border border-slate-700 px-3 py-2 text-left text-xs text-slate-300 hover:bg-slate-800/60 disabled:opacity-50"
        >
          Seed from files
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => handleSeed(true)}
          className="block w-full rounded-lg border border-rose-500/30 px-3 py-2 text-left text-xs text-rose-300 hover:bg-rose-950/30 disabled:opacity-50"
        >
          Force re-seed
        </button>
      </div>
      {message && <p className="mt-2 px-3 text-xs text-emerald-400">{message}</p>}
      {error && <p className="mt-2 px-3 text-xs text-rose-400">{error}</p>}
    </div>
  )
}
