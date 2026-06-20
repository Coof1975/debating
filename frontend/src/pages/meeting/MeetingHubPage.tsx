import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Outlet, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { getExtensionRejected } from '../../api/errors'
import { MeetingHeader } from '../../components/meeting/MeetingHeader'
import { MeetingTabNav } from '../../components/meeting/MeetingTabNav'
import { WorkspaceLayout } from '../../components/WorkspaceLayout'
import { useMeetingStream } from '../../hooks/useMeetingStream'
import { parseHiddenTurns } from '../../lib/hiddenTurns'
import {
  buildExtensionStreamSeed,
  extensionSuggestionLabel,
} from '../../lib/meetingExtension'
import {
  DEFAULT_LLM_PROVIDERS,
  DEFAULT_OPENAI_MODEL,
} from '../../lib/llmOptions'
import { parseSpeakerSelections } from '../../lib/speakerSelections'
import type { ExtensionRejectedDetail, LlmProviderOption, Meeting, SharedFact, WorkingProposal } from '../../types'
import { MeetingHubProvider, type MeetingHubContextValue } from './MeetingHubContext'

export function MeetingHubPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const meetingId = id ?? ''

  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [providers, setProviders] = useState<LlmProviderOption[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [rerunning, setRerunning] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [showRerun, setShowRerun] = useState(false)
  const [showInternalReasoning, setShowInternalReasoning] = useState(true)
  const [showOrchestratorDecisions, setShowOrchestratorDecisions] = useState(false)
  const [providerId, setProviderId] = useState('openai')
  const [modelId, setModelId] = useState(DEFAULT_OPENAI_MODEL)
  const [extending, setExtending] = useState(false)
  const [extensionRejection, setExtensionRejection] = useState<ExtensionRejectedDetail | null>(null)
  const [pendingExtensionContent, setPendingExtensionContent] = useState('')

  const isPending = meeting?.status === 'pending'
  const isStreaming = meeting?.status === 'running'
  const isCompleted = meeting?.status === 'completed'

  const stream = useMeetingStream(meetingId || null, meeting?.status)

  const loadMeeting = useCallback(async () => {
    if (!meetingId) return
    const data = await api.getMeeting(meetingId)
    setMeeting(data)
    const cfg = data.config ?? {}
    const useMock = Boolean(cfg.use_mock)
    setProviderId(useMock ? 'mock' : String(cfg.llm_provider ?? 'openai'))
    setModelId(String(cfg.llm_model ?? DEFAULT_OPENAI_MODEL))
  }, [meetingId])

  useEffect(() => {
    if (!meetingId) return
    setLoading(true)
    loadMeeting()
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
    api.listLlmOptions()
      .then((data) => setProviders(data.providers))
      .catch(() => setProviders(DEFAULT_LLM_PROVIDERS))
  }, [meetingId, loadMeeting])

  useEffect(() => {
    if (stream.insightReport && meetingId) {
      loadMeeting()
    }
  }, [stream.insightReport, meetingId, loadMeeting])

  useEffect(() => {
    if (!meetingId || stream.isLive || !stream.terminationReason) return
    if (meeting?.status === 'running') {
      loadMeeting()
    }
  }, [stream.isLive, stream.terminationReason, meetingId, meeting?.status, loadMeeting])

  const activeProvider = useMemo(
    () => providers.find((p) => p.id === providerId),
    [providers, providerId],
  )

  const turns = isStreaming ? stream.turns : (meeting?.record?.messages ?? [])
  const hiddenTurns = isStreaming
    ? stream.hiddenTurns
    : parseHiddenTurns(meeting?.record?.metadata?.hidden_turns)
  const speakerSelections = isStreaming
    ? stream.speakerSelections
    : parseSpeakerSelections(meeting?.record?.metadata?.speaker_selections)
  const workingProposals: WorkingProposal[] = isStreaming
    ? stream.workingProposals
    : ((meeting?.record?.metadata?.working_proposals as WorkingProposal[] | undefined) ?? [])
  const sharedFacts: SharedFact[] = isStreaming
    ? stream.sharedFacts
    : ((meeting?.record?.metadata?.shared_facts as SharedFact[] | undefined) ?? [])
  const insight = stream.insightReport || meeting?.insight_report || ''
  const displayError = error ?? stream.error ?? meeting?.error_message ?? null

  async function handleStart() {
    if (!meetingId) return
    setStarting(true)
    setError(null)
    try {
      const updated = await api.startMeeting(meetingId)
      setMeeting(updated)
      stream.reset()
      navigate(`/meetings/${meetingId}/simulation`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start simulation')
    } finally {
      setStarting(false)
    }
  }

  async function handleRerun() {
    if (!meetingId) return
    setRerunning(true)
    setError(null)
    try {
      const useMock = providerId === 'mock'
      const updated = await api.rerunMeeting(meetingId, {
        llm_provider: useMock ? 'mock' : providerId,
        llm_model: modelId,
        use_mock: useMock,
      })
      setMeeting(updated)
      setShowRerun(false)
      stream.reset()
      navigate(`/meetings/${meetingId}/simulation`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rerun failed')
    } finally {
      setRerunning(false)
    }
  }

  async function handleDelete() {
    if (!meetingId) return
    if (!window.confirm('Delete this meeting permanently? This cannot be undone.')) {
      return
    }
    setDeleting(true)
    setError(null)
    try {
      await api.deleteMeeting(meetingId)
      navigate('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete')
    } finally {
      setDeleting(false)
    }
  }

  const dismissExtensionRejection = useCallback(() => {
    setExtensionRejection(null)
    setPendingExtensionContent('')
  }, [])

  const handleEvaluateExtension = useCallback(
    async (content: string): Promise<string | null> => {
      if (!meetingId) return null
      const result = await api.evaluateMeetingExtension(meetingId, { content })
      if (result.is_significant) {
        return `Đủ ý nghĩa để mở lại simulation: ${result.reason}`
      }
      return `Chưa đủ ý nghĩa: ${result.reason} — ${extensionSuggestionLabel(result.suggestion)}`
    },
    [meetingId],
  )

  const handleExtend = useCallback(
    async (content: string, force = false) => {
      if (!meetingId || !meeting) return

      if (
        force &&
        !window.confirm(
          'Classifier cho rằng nội dung chưa đủ ý nghĩa. Vẫn tiếp tục mở lại simulation?',
        )
      ) {
        return
      }

      setExtending(true)
      setError(null)
      setExtensionRejection(null)

      const seed = buildExtensionStreamSeed(meeting)

      try {
        const updated = await api.extendMeeting(meetingId, { content, force })
        stream.beginExtension(seed)
        setMeeting(updated)
        setPendingExtensionContent('')
      } catch (err) {
        const rejection = getExtensionRejected(err)
        if (rejection) {
          setExtensionRejection(rejection)
          setPendingExtensionContent(content)
        } else {
          setError(err instanceof Error ? err.message : 'Không thể mở rộng simulation')
        }
      } finally {
        setExtending(false)
      }
    },
    [meeting, meetingId, stream],
  )

  if (loading) {
    return (
      <WorkspaceLayout>
        <p className="text-slate-400">Loading meeting…</p>
      </WorkspaceLayout>
    )
  }

  if (!meeting || !meetingId) {
    return (
      <WorkspaceLayout>
        <p className="text-rose-400">Meeting not found.</p>
        <Link to="/" className="mt-4 text-indigo-400">
          Back to list
        </Link>
      </WorkspaceLayout>
    )
  }

  const hubValue: MeetingHubContextValue = {
    meetingId,
    meeting,
    setMeeting,
    loadMeeting,
    error,
    setError,
    providers,
    providerId,
    setProviderId,
    modelId,
    setModelId,
    activeProvider,
    isPending,
    isStreaming,
    isCompleted,
    stream,
    turns,
    hiddenTurns,
    showInternalReasoning,
    setShowInternalReasoning,
    showOrchestratorDecisions,
    setShowOrchestratorDecisions,
    speakerSelections,
    workingProposals,
    sharedFacts,
    insight,
    displayError,
    starting,
    handleStart,
    rerunning,
    showRerun,
    setShowRerun,
    handleRerun,
    deleting,
    handleDelete,
    extending,
    extensionRejection,
    pendingExtensionContent,
    handleExtend,
    handleEvaluateExtension,
    dismissExtensionRejection,
  }

  return (
    <MeetingHubProvider value={hubValue}>
      <WorkspaceLayout>
        <MeetingHeader
          meeting={meeting}
          onDelete={handleDelete}
          deleting={deleting}
        />
        <MeetingTabNav meetingId={meetingId} status={meeting.status} />
        <Outlet />
      </WorkspaceLayout>
    </MeetingHubProvider>
  )
}

export function MeetingHubIndexRedirect() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/meetings/${id}/overview`} replace />
}
