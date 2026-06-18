import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { AdminLayout } from '../components/AdminLayout'
import type { NegotiationProfile, PersonaSection } from '../types'

const inputClass =
  'w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-white'
const labelClass = 'block text-sm font-medium text-slate-300'

const DEFAULT_NEGOTIATION: NegotiationProfile = {
  compromise_threshold: 0.5,
  min_interest_retention: 0.7,
  director_sensitivity: 0.6,
  deadlock_tolerance: 0.3,
}

const ROLE_NEGOTIATION_DEFAULTS: Record<string, NegotiationProfile> = {
  CFO: { compromise_threshold: 0.25, min_interest_retention: 0.85, director_sensitivity: 0.45, deadlock_tolerance: 0.2 },
  PRODUCT: { compromise_threshold: 0.35, min_interest_retention: 0.75, director_sensitivity: 0.5, deadlock_tolerance: 0.25 },
  MARKETING: { compromise_threshold: 0.55, min_interest_retention: 0.65, director_sensitivity: 0.65, deadlock_tolerance: 0.4 },
  SALE: { compromise_threshold: 0.65, min_interest_retention: 0.6, director_sensitivity: 0.7, deadlock_tolerance: 0.45 },
  CEO: { compromise_threshold: 0.7, min_interest_retention: 0.55, director_sensitivity: 0.85, deadlock_tolerance: 0.35 },
}

function emptySection(): PersonaSection {
  return { key: '', title: '', content: '' }
}

export function PersonaEditPage() {
  const { role: roleParam } = useParams<{ role: string }>()
  const isNew = roleParam === 'new' || !roleParam
  const navigate = useNavigate()

  const [loading, setLoading] = useState(!isNew)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [role, setRole] = useState('')
  const [displayTitle, setDisplayTitle] = useState('')
  const [name, setName] = useState('')
  const [age, setAge] = useState<string>('')
  const [toneOfVoice, setToneOfVoice] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [sections, setSections] = useState<PersonaSection[]>([emptySection()])
  const [negotiation, setNegotiation] = useState<NegotiationProfile>(DEFAULT_NEGOTIATION)
  const [previewPrompt, setPreviewPrompt] = useState<string | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [showPreview, setShowPreview] = useState(false)

  useEffect(() => {
    if (isNew || !roleParam) return
    setLoading(true)
    api
      .getPersona(roleParam)
      .then((persona) => {
        setRole(persona.role)
        setDisplayTitle(persona.display_title)
        setName(persona.name)
        setAge(persona.age != null ? String(persona.age) : '')
        setToneOfVoice(persona.tone_of_voice)
        setIsActive(persona.is_active)
        const sectionList = Object.values(persona.sections ?? {})
        setSections(sectionList.length > 0 ? sectionList : [emptySection()])
        setNegotiation(persona.negotiation ?? ROLE_NEGOTIATION_DEFAULTS[persona.role] ?? DEFAULT_NEGOTIATION)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [isNew, roleParam])

  function updateSection(index: number, field: keyof PersonaSection, value: string) {
    setSections((prev) =>
      prev.map((section, i) => {
        if (i !== index) return section
        const updated = { ...section, [field]: value }
        if (field === 'key') {
          updated.key = value.toUpperCase().replace(/\s+/g, '_')
        }
        return updated
      }),
    )
  }

  function buildSectionsPayload(): Record<string, PersonaSection> {
    const result: Record<string, PersonaSection> = {}
    for (const section of sections) {
      const key = section.key.trim()
      if (!key) continue
      result[key] = { ...section, key }
    }
    return result
  }

  function updateNegotiation(field: keyof NegotiationProfile, value: number) {
    setNegotiation((prev) => ({ ...prev, [field]: value }))
  }

  function applyRoleNegotiationDefaults(nextRole: string) {
    const key = nextRole.trim().toUpperCase()
    if (ROLE_NEGOTIATION_DEFAULTS[key]) {
      setNegotiation(ROLE_NEGOTIATION_DEFAULTS[key])
    }
  }

  async function handlePreviewPrompt() {
    if (isNew || !roleParam) return
    setPreviewLoading(true)
    setError(null)
    try {
      const result = await api.previewPersonaPrompt(roleParam)
      setPreviewPrompt(result.system_prompt)
      setShowPreview(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview prompt')
    } finally {
      setPreviewLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!displayTitle.trim()) {
      setError('Display title is required.')
      return
    }
    if (isNew && !role.trim()) {
      setError('Role is required.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const sectionsPayload = buildSectionsPayload()

      if (isNew) {
        await api.createPersona({
          role: role.trim(),
          display_title: displayTitle.trim(),
          name: name.trim(),
          age: age ? Number(age) : null,
          tone_of_voice: toneOfVoice,
          is_active: isActive,
          sections: sectionsPayload,
          negotiation,
        })
      } else {
        await api.updatePersona(roleParam!, {
          display_title: displayTitle.trim(),
          name: name.trim(),
          age: age ? Number(age) : null,
          tone_of_voice: toneOfVoice,
          is_active: isActive,
          sections: sectionsPayload,
          negotiation,
        })
      }
      navigate('/admin/personas')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <AdminLayout>
        <p className="text-slate-400">Loading persona…</p>
      </AdminLayout>
    )
  }

  return (
    <AdminLayout>
      <Link to="/admin/personas" className="text-sm text-slate-500 hover:text-slate-300">
        ← All personas
      </Link>
      <h1 className="mt-2 text-2xl font-semibold text-white">
        {isNew ? 'New persona' : `Edit ${role}`}
      </h1>

      <form onSubmit={handleSubmit} className="mt-8 space-y-8">
        <section className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <label className={labelClass}>Role</label>
            <input
              value={role}
              onChange={(e) => {
                const next = e.target.value.toUpperCase()
                setRole(next)
                if (isNew) applyRoleNegotiationDefaults(next)
              }}
              className={inputClass}
              required
              disabled={!isNew}
              placeholder="CEO"
            />
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Display title</label>
            <input
              value={displayTitle}
              onChange={(e) => setDisplayTitle(e.target.value)}
              className={inputClass}
              required
            />
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </div>
          <div className="space-y-2">
            <label className={labelClass}>Age</label>
            <input
              type="number"
              min={1}
              max={120}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className={inputClass}
            />
          </div>
        </section>

        <section className="space-y-2">
          <label className={labelClass}>Tone of voice</label>
          <textarea
            value={toneOfVoice}
            onChange={(e) => setToneOfVoice(e.target.value)}
            rows={3}
            className={inputClass}
          />
        </section>

        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
          />
          Active (available for new meetings)
        </label>

        <section className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <h2 className="text-lg font-medium text-white">Hồ sơ đàm phán</h2>
          <p className="text-sm text-slate-400">
            Điều chỉnh mức thỏa hiệp và áp lực từ Sếp khi agent suy nghĩ trong cuộc họp.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            {(
              [
                ['compromise_threshold', 'Chỉ số thỏa hiệp', '0 = cực cứng, 1 = dễ nhượng'],
                ['min_interest_retention', 'Giữ lợi ích bộ phận', 'Tối thiểu % lợi ích cần giữ'],
                ['director_sensitivity', 'Nhạy cảm áp lực Sếp', 'Cao = dễ nhún khi họp bế tắc'],
                ['deadlock_tolerance', 'Chịu bế tắc', 'Cao = chấp nhận tranh lâu hơn'],
              ] as const
            ).map(([field, label, hint]) => (
              <div key={field} className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <label className={labelClass}>{label}</label>
                  <span className="text-xs text-slate-400">{negotiation[field].toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={negotiation[field]}
                  onChange={(e) => updateNegotiation(field, Number(e.target.value))}
                  className="w-full"
                />
                <p className="text-xs text-slate-500">{hint}</p>
              </div>
            ))}
          </div>
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
              <div className="grid gap-3 sm:grid-cols-2">
                <input
                  value={section.key}
                  onChange={(e) => updateSection(index, 'key', e.target.value)}
                  className={inputClass}
                  placeholder="Key (e.g. identity)"
                />
                <input
                  value={section.title}
                  onChange={(e) => updateSection(index, 'title', e.target.value)}
                  className={inputClass}
                  placeholder="Title"
                />
              </div>
              <textarea
                value={section.content}
                onChange={(e) => updateSection(index, 'content', e.target.value)}
                rows={5}
                className={inputClass}
                placeholder="Content"
              />
            </div>
          ))}
        </section>

        {error && <p className="text-sm text-rose-400">{error}</p>}

        {!isNew && (
          <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
            <button
              type="button"
              onClick={handlePreviewPrompt}
              disabled={previewLoading}
              className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              {previewLoading ? 'Generating…' : 'Xem system prompt'}
            </button>
            {showPreview && previewPrompt && (
              <textarea
                readOnly
                value={previewPrompt}
                rows={16}
                className={`${inputClass} mt-4 font-mono text-xs leading-relaxed`}
              />
            )}
          </section>
        )}

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={saving}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {saving ? 'Saving…' : isNew ? 'Create persona' : 'Save changes'}
          </button>
          <Link to="/admin/personas" className="px-3 py-2.5 text-sm text-slate-400 hover:text-white">
            Cancel
          </Link>
        </div>
      </form>
    </AdminLayout>
  )
}
