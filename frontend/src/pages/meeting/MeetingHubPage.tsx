import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Outlet, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client'
import { MeetingHeader } from '../../components/meeting/MeetingHeader'
import { MeetingTabNav } from '../../components/meeting/MeetingTabNav'
import { WorkspaceLayout } from '../../components/WorkspaceLayout'
import { useMeetingStream } from '../../hooks/useMeetingStream'
import { parseHiddenTurns } from '../../lib/hiddenTurns'
import { parseSpeakerSelections } from '../../lib/speakerSelections'
import type { LlmProviderOption, Meeting, SharedFact, WorkingProposal } from '../../types'
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
  const [modelId, setModelId] = useState('gpt-4o-mini')

  const isPending = meeting?.status === 'pending'
  const isStreaming = meeting?.status === 'running'
  const isCompleted = meeting?.status === 'completed'

  const stream = useMeetingStream(
    isStreaming ? meetingId : null,
    isStreaming ? meeting?.status : undefined,
  )

  const loadMeeting = useCallback(async () => {
    if (!meetingId) return
    const data = await api.getMeeting(meetingId)
    setMeeting(data)
    const cfg = data.config ?? {}
    const useMock = Boolean(cfg.use_mock)
    setProviderId(useMock ? 'mock' : String(cfg.llm_provider ?? 'openai'))
    setModelId(String(cfg.llm_model ?? 'gpt-4o-mini'))
  }, [meetingId])

  useEffect(() => {
    if (!meetingId) return
    setLoading(true)
    loadMeeting()
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
    api.listLlmOptions().then((data) => setProviders(data.providers))
  }, [meetingId, loadMeeting])

  useEffect(() => {
    if (stream.insightReport && meetingId) {
      loadMeeting()
    }
  }, [stream.insightReport, meetingId, loadMeeting])

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
