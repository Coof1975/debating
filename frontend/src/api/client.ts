import type {
  ChatMessage,
  ChatSession,
  CompanyProfile,
  CompanyProfileUpdatePayload,
  CreateMeetingPayload,
  ExtendMeetingPayload,
  ExtensionSignificanceResponse,
  LlmProviderOption,
  Meeting,
  MeetingListItem,
  Persona,
  PersonaCreatePayload,
  PersonaListItem,
  PersonaUpdatePayload,
  PromptPreview,
  RebuildPromptsResult,
  RerunMeetingPayload,
  SeedDatabaseResult,
  SendChatMessageResponse,
  UpdateMeetingPayload,
} from '../types'
import { ApiRequestError } from './errors'

/** Local dev: empty → Vite proxies /api to localhost:8000. Cloud: set VITE_API_BASE_URL. */
const API_BASE = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? ''
const API = API_BASE ? `${API_BASE}/api` : '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options?.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const detail = (body as { detail?: unknown }).detail
    let message = response.statusText
    if (typeof detail === 'string') {
      message = detail
    } else if (detail && typeof detail === 'object' && 'reason' in detail) {
      message = String((detail as { reason?: string }).reason ?? response.statusText)
    }
    throw new ApiRequestError(message, response.status, detail)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return response.json() as Promise<T>
}

export const api = {
  listMeetings: (params?: { status?: string; q?: string; limit?: number }) => {
    const search = new URLSearchParams()
    if (params?.status) search.set('status', params.status)
    if (params?.q) search.set('q', params.q)
    if (params?.limit) search.set('limit', String(params.limit))
    const query = search.toString()
    return request<MeetingListItem[]>(`/meetings${query ? `?${query}` : ''}`)
  },
  getMeeting: (id: string) => request<Meeting>(`/meetings/${id}`),
  createMeeting: (payload: CreateMeetingPayload) =>
    request<Meeting>('/meetings', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateMeeting: (id: string, payload: UpdateMeetingPayload) =>
    request<Meeting>(`/meetings/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  startMeeting: (id: string) =>
    request<Meeting>(`/meetings/${id}/start`, { method: 'POST' }),
  rerunMeeting: (id: string, payload?: RerunMeetingPayload) =>
    request<Meeting>(`/meetings/${id}/rerun`, {
      method: 'POST',
      body: JSON.stringify(payload ?? {}),
    }),
  evaluateMeetingExtension: (id: string, payload: ExtendMeetingPayload) =>
    request<ExtensionSignificanceResponse>(`/meetings/${id}/extend/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ content: payload.content }),
    }),
  extendMeeting: (id: string, payload: ExtendMeetingPayload) =>
    request<Meeting>(`/meetings/${id}/extend`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  deleteMeeting: (id: string) =>
    request<void>(`/meetings/${id}`, { method: 'DELETE' }),
  listPersonas: (activeOnly = true) =>
    request<PersonaListItem[]>(`/personas?active_only=${activeOnly}`),
  getPersona: (role: string) => request<Persona>(`/personas/${encodeURIComponent(role)}`),
  createPersona: (payload: PersonaCreatePayload) =>
    request<Persona>('/personas', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updatePersona: (role: string, payload: PersonaUpdatePayload) =>
    request<Persona>(`/personas/${encodeURIComponent(role)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  deletePersona: (role: string) =>
    request<void>(`/personas/${encodeURIComponent(role)}`, { method: 'DELETE' }),
  getCompanyProfile: () => request<CompanyProfile>('/company-profile'),
  updateCompanyProfile: (payload: CompanyProfileUpdatePayload) =>
    request<CompanyProfile>('/company-profile', {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
  rebuildPrompts: () =>
    request<RebuildPromptsResult>('/company-profile/rebuild-prompts', { method: 'POST' }),
  previewPersonaPrompt: (role: string, meetingTopic?: string) => {
    const query = meetingTopic
      ? `?${new URLSearchParams({ meeting_topic: meetingTopic }).toString()}`
      : ''
    return request<PromptPreview>(
      `/personas/${encodeURIComponent(role)}/preview-prompt${query}`,
      { method: 'POST' },
    )
  },
  seedDatabase: (force = false) =>
    request<SeedDatabaseResult>(`/admin/seed?force=${force}`, { method: 'POST' }),
  listLlmOptions: () =>
    request<{ providers: LlmProviderOption[] }>('/llm/options'),

  listChatSessions: (meetingId: string) =>
    request<ChatSession[]>(`/meetings/${meetingId}/chat/sessions`),
  createChatSession: (meetingId: string, personaId: string) =>
    request<ChatSession>(`/meetings/${meetingId}/chat/sessions`, {
      method: 'POST',
      body: JSON.stringify({ persona_id: personaId }),
    }),
  listChatMessages: (meetingId: string, sessionId: string) =>
    request<ChatMessage[]>(`/meetings/${meetingId}/chat/sessions/${sessionId}/messages`),
  sendChatMessage: (meetingId: string, sessionId: string, content: string) =>
    request<SendChatMessageResponse>(
      `/meetings/${meetingId}/chat/sessions/${sessionId}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      },
    ),
}

export { ApiRequestError, getExtensionRejected } from './errors'

export function streamMeeting(
  meetingId: string,
  onEvent: (event: { type: string; data: Record<string, unknown> }) => void,
  onError?: (error: Error) => void,
): () => void {
  const source = new EventSource(`${API}/meetings/${meetingId}/stream`)

  source.onmessage = (message) => {
    try {
      const event = JSON.parse(message.data) as { type: string; data: Record<string, unknown> }
      onEvent(event)
      // Insight is emitted after "completed"; closing early drops the report.
      if (event.type === 'insight' || event.type === 'error') {
        source.close()
      }
    } catch (err) {
      onError?.(err instanceof Error ? err : new Error('Invalid stream event'))
    }
  }

  source.onerror = () => {
    onError?.(new Error('Stream connection lost'))
    source.close()
  }

  return () => source.close()
}
