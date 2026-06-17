import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { AdminLayout } from '../components/AdminLayout'
import { formatDate } from '../lib/utils'
import type { CompanySection } from '../types'

const inputClass =
  'w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white'
const labelClass = 'block text-sm font-medium text-slate-300'

function emptySection(): CompanySection {
  return { key: '', title: '', content: '', perspective: '' }
}

export function CompanyProfilePage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)

  const [companyName, setCompanyName] = useState('')
  const [reportPeriod, setReportPeriod] = useState('')
  const [source, setSource] = useState('')
  const [sections, setSections] = useState<CompanySection[]>([emptySection()])
  const [rebuilding, setRebuilding] = useState(false)

  useEffect(() => {
    api
      .getCompanyProfile()
      .then((profile) => {
        setCompanyName(profile.company_name)
        setReportPeriod(profile.report_period)
        setSource(profile.source)
        setUpdatedAt(profile.updated_at)
        const sectionList = Object.values(profile.sections ?? {})
        setSections(sectionList.length > 0 ? sectionList : [emptySection()])
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  function updateSection(index: number, field: keyof CompanySection, value: string) {
    setSections((prev) =>
      prev.map((section, i) => {
        if (i !== index) return section
        const updated = { ...section, [field]: value }
        if (field === 'key') {
          updated.key = value.toLowerCase().replace(/\s+/g, '_')
        }
        return updated
      }),
    )
  }

  function buildSectionsPayload(): Record<string, CompanySection> {
    const result: Record<string, CompanySection> = {}
    for (const section of sections) {
      const key = section.key.trim()
      if (!key) continue
      result[key] = { ...section, key }
    }
    return result
  }

  async function handleRebuildPrompts() {
    setRebuilding(true)
    setError(null)
    setSuccess(null)
    try {
      const result = await api.rebuildPrompts()
      setSuccess(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to rebuild prompts')
    } finally {
      setRebuilding(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!companyName.trim()) {
      setError('Company name is required.')
      return
    }
    setSaving(true)
    setError(null)
    setSuccess(null)
    try {
      const profile = await api.updateCompanyProfile({
        company_name: companyName.trim(),
        report_period: reportPeriod,
        source,
        sections: buildSectionsPayload(),
      })
      setUpdatedAt(profile.updated_at)
      setSuccess('Company profile saved. Persona prompts were rebuilt automatically.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <AdminLayout>
        <p className="text-slate-400">Loading company profile…</p>
      </AdminLayout>
    )
  }

  return (
    <AdminLayout>
      <h1 className="text-2xl font-semibold text-white">Company profile</h1>
      <p className="mt-1 text-slate-400">
        Edit the business context used to generate persona prompts for meetings.
      </p>
      {updatedAt && (
        <p className="mt-2 text-xs text-slate-500">Last updated {formatDate(updatedAt)}</p>
      )}

      <div className="mt-6 rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 text-sm text-amber-100">
        <p>
          Thay đổi company profile sẽ tự rebuild prompt khi lưu. Bạn cũng có thể rebuild thủ công
          cho tất cả persona.
        </p>
        <button
          type="button"
          onClick={handleRebuildPrompts}
          disabled={rebuilding}
          className="mt-3 rounded-lg border border-amber-500/40 px-4 py-2 text-sm text-amber-100 hover:bg-amber-950/40 disabled:opacity-50"
        >
          {rebuilding ? 'Rebuilding…' : 'Rebuild all persona prompts'}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="mt-8 space-y-8">
        <section className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Company name</label>
            <input
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className={inputClass}
              required
            />
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Report period</label>
            <input
              value={reportPeriod}
              onChange={(e) => setReportPeriod(e.target.value)}
              className={inputClass}
              placeholder="Q2/2026"
            />
          </div>
        </section>

        <section className="space-y-2">
          <label className={labelClass}>Source</label>
          <input
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className={inputClass}
            placeholder="Data source description"
          />
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-medium text-white">Sections</h2>
            <button
              type="button"
              onClick={() => setSections((prev) => [...prev, emptySection()])}
              className="text-sm text-indigo-400 hover:text-indigo-300"
            >
              + Add section
            </button>
          </div>
          {sections.map((section, index) => (
            <div
              key={index}
              className="space-y-3 rounded-xl border border-slate-800 bg-slate-900/40 p-4"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-400">Section {index + 1}</span>
                {sections.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setSections((prev) => prev.filter((_, i) => i !== index))}
                    className="text-xs text-rose-400 hover:text-rose-300"
                  >
                    Remove
                  </button>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <input
                  value={section.key}
                  onChange={(e) => updateSection(index, 'key', e.target.value)}
                  className={inputClass}
                  placeholder="Key"
                />
                <input
                  value={section.title}
                  onChange={(e) => updateSection(index, 'title', e.target.value)}
                  className={inputClass}
                  placeholder="Title"
                />
                <input
                  value={section.perspective}
                  onChange={(e) => updateSection(index, 'perspective', e.target.value)}
                  className={inputClass}
                  placeholder="Perspective (e.g. CFO)"
                />
              </div>
              <textarea
                value={section.content}
                onChange={(e) => updateSection(index, 'content', e.target.value)}
                rows={6}
                className={inputClass}
                placeholder="Content"
              />
            </div>
          ))}
        </section>

        {error && <p className="text-sm text-rose-400">{error}</p>}
        {success && (
          <p className="text-sm text-emerald-400">{success}</p>
        )}

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save company profile'}
        </button>
      </form>
    </AdminLayout>
  )
}
