import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { LlmProviderOption, PersonaListItem } from '../../types'

type WizardData = {
  topic: string
  scheduledDate: string
  scheduledTime: string
  notes: string
  openingMessage: string
  selected: string[]
  hostId: string
  maxTurns: number
  providerId: string
  modelId: string
}

const inputClass = 'input-field'

function defaultDate(): string {
  return new Date().toISOString().slice(0, 10)
}

function defaultTime(): string {
  const d = new Date()
  d.setHours(d.getHours() + 1, 0, 0, 0)
  return d.toTimeString().slice(0, 5)
}

function toScheduledIso(date: string, time: string): string | undefined {
  if (!date.trim()) return undefined
  const value = new Date(`${date}T${time || '09:00'}`)
  if (Number.isNaN(value.getTime())) return undefined
  return value.toISOString()
}

export function MeetingWizard() {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [personas, setPersonas] = useState<PersonaListItem[]>([])
  const [providers, setProviders] = useState<LlmProviderOption[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const [data, setData] = useState<WizardData>({
    topic: '',
    scheduledDate: defaultDate(),
    scheduledTime: defaultTime(),
    notes: '',
    openingMessage: '',
    selected: [],
    hostId: '',
    maxTurns: 25,
    providerId: 'openai',
    modelId: 'gpt-4o-mini',
  })

  const activeProvider = useMemo(
    () => providers.find((p) => p.id === data.providerId),
    [providers, data.providerId],
  )

  useEffect(() => {
    api.listPersonas().then((rows) => {
      const roles = rows.map((p) => p.role)
      const defaultHost = roles.includes('CEO') ? 'CEO' : (roles[0] ?? '')
      setPersonas(rows)
      setData((prev) => ({
        ...prev,
        selected: roles,
        hostId: prev.hostId || defaultHost,
      }))
    })
    api.listLlmOptions().then((res) => {
      setProviders(res.providers)
      const defaultProvider = res.providers[0]
      if (defaultProvider) {
        setData((prev) => ({
          ...prev,
          providerId: defaultProvider.id,
          modelId: defaultProvider.default_model,
        }))
      }
    })
  }, [])

  useEffect(() => {
    if (activeProvider) {
      setData((prev) => ({ ...prev, modelId: activeProvider.default_model }))
    }
  }, [activeProvider])

  function togglePersona(role: string) {
    setData((prev) => {
      const selected = prev.selected.includes(role)
        ? prev.selected.filter((r) => r !== role)
        : [...prev.selected, role]
      let hostId = prev.hostId
      if (!selected.includes(hostId)) {
        hostId = selected.includes('CEO') ? 'CEO' : (selected[0] ?? '')
      }
      return { ...prev, selected, hostId }
    })
  }

  function validateStep(current: number): string | null {
    if (current === 1 && !data.topic.trim()) {
      return 'Nhập chủ đề cuộc họp.'
    }
    if (current === 2) {
      if (data.selected.length === 0) return 'Chọn ít nhất một persona.'
      if (!data.hostId || !data.selected.includes(data.hostId)) {
        return 'Chọn người chủ trì trong danh sách tham gia.'
      }
    }
    return null
  }

  function goNext() {
    const message = validateStep(step)
    if (message) {
      setError(message)
      return
    }
    setError(null)
    setStep((s) => Math.min(3, s + 1))
  }

  function goBack() {
    setError(null)
    setStep((s) => Math.max(1, s - 1))
  }

  async function handleSubmit() {
    const message = validateStep(2)
    if (message) {
      setError(message)
      setStep(2)
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const useMock = data.providerId === 'mock'
      const meeting = await api.createMeeting({
        topic: data.topic.trim(),
        opening_message: data.openingMessage.trim() || undefined,
        notes: data.notes.trim() || undefined,
        scheduled_at: toScheduledIso(data.scheduledDate, data.scheduledTime),
        participant_ids: data.selected,
        host_id: data.hostId,
        max_turns: data.maxTurns,
        llm_provider: useMock ? 'openai' : data.providerId,
        llm_model: data.modelId,
        use_mock: useMock,
        auto_start: false,
      })
      navigate(`/meetings/${meeting.id}/overview`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create meeting')
    } finally {
      setSubmitting(false)
    }
  }

  const steps = ['Thông tin', 'Thành phần', 'Xác nhận']

  return (
    <div>
      <div className="mb-6 flex flex-col gap-2 sm:mb-8 sm:flex-row sm:items-center sm:gap-2">
        {steps.map((label, index) => {
          const n = index + 1
          const active = step === n
          const done = step > n
          return (
            <div key={label} className="flex items-center gap-2">
              {index > 0 && <div className="hidden h-px w-8 bg-slate-700 sm:block" />}
              <div
                className={`flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm sm:w-auto sm:rounded-full sm:py-1 ${
                  active
                    ? 'bg-indigo-600 text-white'
                    : done
                      ? 'bg-slate-700 text-slate-200'
                      : 'bg-slate-800 text-slate-500'
                }`}
              >
                <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-black/20 text-xs font-semibold">
                  {n}
                </span>
                <span className="font-medium">{label}</span>
              </div>
            </div>
          )
        })}
      </div>

      {step === 1 && (
        <section className="space-y-6">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">
              Chủ đề cuộc họp *
            </label>
            <input
              value={data.topic}
              onChange={(e) => setData((prev) => ({ ...prev, topic: e.target.value }))}
              className={inputClass}
              placeholder="VD: Kế hoạch thúc đẩy bán hàng Keos Q3"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-300">Ngày dự kiến</label>
              <input
                type="date"
                value={data.scheduledDate}
                onChange={(e) => setData((prev) => ({ ...prev, scheduledDate: e.target.value }))}
                className={inputClass}
              />
            </div>
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-300">Giờ dự kiến</label>
              <input
                type="time"
                value={data.scheduledTime}
                onChange={(e) => setData((prev) => ({ ...prev, scheduledTime: e.target.value }))}
                className={inputClass}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">Ghi chú thêm</label>
            <textarea
              value={data.notes}
              onChange={(e) => setData((prev) => ({ ...prev, notes: e.target.value }))}
              rows={3}
              className={inputClass}
              placeholder="Bối cảnh nội bộ, mục tiêu phụ…"
            />
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">
              Lời mở đầu cuộc họp (tùy chọn)
            </label>
            <textarea
              value={data.openingMessage}
              onChange={(e) => setData((prev) => ({ ...prev, openingMessage: e.target.value }))}
              rows={3}
              className={inputClass}
              placeholder="Mandate từ chủ trì — dùng khi chạy simulation"
            />
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-6">
          <div className="space-y-3">
            <label className="block text-sm font-medium text-slate-300">
              Persona tham gia *
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              {personas.map((persona) => (
                <label
                  key={persona.role}
                  className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-900/50 p-3"
                >
                  <input
                    type="checkbox"
                    checked={data.selected.includes(persona.role)}
                    onChange={() => togglePersona(persona.role)}
                  />
                  <div>
                    <div className="font-medium text-white">{persona.role}</div>
                    <div className="text-xs text-slate-400">
                      {persona.name || persona.display_title}
                    </div>
                  </div>
                </label>
              ))}
            </div>
          </div>
          <div className="space-y-3">
            <label className="block text-sm font-medium text-slate-300">
              Người chủ trì *
            </label>
            <div className="flex flex-wrap gap-3">
              {data.selected.map((role) => (
                <label
                  key={role}
                  className="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-700 px-3 py-2"
                >
                  <input
                    type="radio"
                    name="host"
                    checked={data.hostId === role}
                    onChange={() => setData((prev) => ({ ...prev, hostId: role }))}
                  />
                  <span className="text-sm text-white">{role}</span>
                </label>
              ))}
            </div>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="space-y-6">
          <div className="card-padded bg-slate-900/50 text-sm text-slate-300">
            <dl className="space-y-3">
              <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                <dt className="shrink-0 text-slate-500 sm:w-32">Chủ đề</dt>
                <dd className="text-white">{data.topic}</dd>
              </div>
              <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                <dt className="shrink-0 text-slate-500 sm:w-32">Lịch</dt>
                <dd>
                  {data.scheduledDate} {data.scheduledTime}
                </dd>
              </div>
              <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                <dt className="shrink-0 text-slate-500 sm:w-32">Chủ trì</dt>
                <dd>{data.hostId}</dd>
              </div>
              <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                <dt className="shrink-0 text-slate-500 sm:w-32">Tham gia</dt>
                <dd>{data.selected.join(', ')}</dd>
              </div>
              {data.notes && (
                <div className="flex flex-col gap-1 sm:flex-row sm:gap-2">
                  <dt className="shrink-0 text-slate-500 sm:w-32">Ghi chú</dt>
                  <dd>{data.notes}</dd>
                </div>
              )}
            </dl>
          </div>

          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="text-sm text-indigo-400 hover:text-indigo-300"
          >
            {showAdvanced ? 'Ẩn cấu hình simulation' : 'Cấu hình simulation (nâng cao)'}
          </button>

          {showAdvanced && (
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">LLM provider</label>
                <select
                  value={data.providerId}
                  onChange={(e) => setData((prev) => ({ ...prev, providerId: e.target.value }))}
                  className={inputClass}
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>{p.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">Model</label>
                <select
                  value={data.modelId}
                  onChange={(e) => setData((prev) => ({ ...prev, modelId: e.target.value }))}
                  className={inputClass}
                >
                  {(activeProvider?.models ?? []).map((m) => (
                    <option key={m.id} value={m.id}>{m.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <label className="block text-sm font-medium text-slate-300">Max turns</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={data.maxTurns}
                  onChange={(e) =>
                    setData((prev) => ({ ...prev, maxTurns: Number(e.target.value) }))
                  }
                  className={inputClass}
                />
              </div>
            </div>
          )}

          <p className="text-sm text-slate-500">
            Meeting sẽ được tạo ở trạng thái chờ. Bạn chạy simulation sau từ trang chi tiết.
          </p>
        </section>
      )}

      {error && <p className="mt-6 text-sm text-rose-400">{error}</p>}

      <div className="mt-8 flex flex-col gap-2 sm:flex-row sm:gap-3">
        {step > 1 && (
          <button
            type="button"
            onClick={goBack}
            className="btn-secondary"
          >
            Quay lại
          </button>
        )}
        {step < 3 ? (
          <button
            type="button"
            onClick={goNext}
            className="btn-primary"
          >
            Tiếp tục
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="btn-primary"
          >
            {submitting ? 'Đang tạo…' : 'Tạo meeting'}
          </button>
        )}
      </div>
    </div>
  )
}
