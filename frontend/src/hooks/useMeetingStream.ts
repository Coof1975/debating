import { useCallback, useEffect, useRef, useState } from 'react'
import type { ExtensionStreamSeed } from '../lib/meetingExtension'
import { parseHiddenTurns } from '../lib/hiddenTurns'
import { parseSpeakerSelections } from '../lib/speakerSelections'
import type { DialogueTurn, HiddenTurn, SharedFact, SpeakerSelection, WorkingProposal } from '../types'
import { streamMeeting } from '../api/client'

type StreamState = {
  turns: DialogueTurn[]
  hiddenTurns: HiddenTurn[]
  speakerSelections: SpeakerSelection[]
  workingProposals: WorkingProposal[]
  sharedFacts: SharedFact[]
  insightReport: string
  statusText: string
  terminationReason: string | null
  isLive: boolean
  error: string | null
}

function parseWorkingProposals(data: Record<string, unknown>): WorkingProposal[] {
  const raw = data.proposals
  if (!Array.isArray(raw)) return []
  return raw as WorkingProposal[]
}

function parseSharedFacts(data: Record<string, unknown>): SharedFact[] {
  const raw = data.facts
  if (!Array.isArray(raw)) return []
  return raw as SharedFact[]
}

function parseHiddenTurnEvent(data: Record<string, unknown>): HiddenTurn | null {
  const parsed = parseHiddenTurns([data])
  return parsed[0] ?? null
}

function parseHiddenTurnsFromRecord(data: Record<string, unknown>): HiddenTurn[] {
  const record = data.record
  if (!record || typeof record !== 'object') return []
  const metadata = (record as Record<string, unknown>).metadata
  if (!metadata || typeof metadata !== 'object') return []
  return parseHiddenTurns((metadata as Record<string, unknown>).hidden_turns)
}

function parseSpeakerSelectionEvent(data: Record<string, unknown>): SpeakerSelection | null {
  const parsed = parseSpeakerSelections([data])
  return parsed[0] ?? null
}

function parseSpeakerSelectionsFromRecord(data: Record<string, unknown>): SpeakerSelection[] {
  const record = data.record
  if (!record || typeof record !== 'object') return []
  const metadata = (record as Record<string, unknown>).metadata
  if (!metadata || typeof metadata !== 'object') return []
  return parseSpeakerSelections((metadata as Record<string, unknown>).speaker_selections)
}

function turnKey(turn: DialogueTurn): string {
  return `${turn.turn_index}:${turn.speaker_id}`
}

function appendUniqueTurns(existing: DialogueTurn[], incoming: DialogueTurn): DialogueTurn[] {
  const key = turnKey(incoming)
  if (existing.some((turn) => turnKey(turn) === key)) {
    return existing
  }
  return [...existing, incoming]
}

export function useMeetingStream(meetingId: string | null, meetingStatus: string | undefined) {
  const [state, setState] = useState<StreamState>({
    turns: [],
    hiddenTurns: [],
    speakerSelections: [],
    workingProposals: [],
    sharedFacts: [],
    insightReport: '',
    statusText: '',
    terminationReason: null,
    isLive: false,
    error: null,
  })
  const disconnectRef = useRef<(() => void) | null>(null)
  const isLiveRef = useRef(false)

  const reset = useCallback(() => {
    isLiveRef.current = false
    setState({
      turns: [],
      hiddenTurns: [],
      speakerSelections: [],
      workingProposals: [],
      sharedFacts: [],
      insightReport: '',
      statusText: '',
      terminationReason: null,
      isLive: false,
      error: null,
    })
  }, [])

  const handleStreamEvent = useCallback((event: { type: string; data: Record<string, unknown> }) => {
    if (event.type === 'turn') {
      const turn = event.data as DialogueTurn
      setState((prev) => ({
        ...prev,
        turns: appendUniqueTurns(prev.turns, turn),
        statusText: `Turn ${turn.turn_index}`,
      }))
    } else if (event.type === 'monologue') {
      const hidden = parseHiddenTurnEvent(event.data)
      if (!hidden) return
      setState((prev) => ({
        ...prev,
        hiddenTurns: [...prev.hiddenTurns, hidden],
      }))
    } else if (event.type === 'orchestrator') {
      const selection = parseSpeakerSelectionEvent(event.data)
      if (!selection) return
      setState((prev) => ({
        ...prev,
        speakerSelections: [...prev.speakerSelections, selection],
      }))
    } else if (event.type === 'proposal_update') {
      setState((prev) => ({
        ...prev,
        workingProposals: parseWorkingProposals(event.data),
      }))
    } else if (event.type === 'fact_update') {
      setState((prev) => ({
        ...prev,
        sharedFacts: parseSharedFacts(event.data),
      }))
    } else if (event.type === 'insight') {
      setState((prev) => ({
        ...prev,
        insightReport: String(event.data.insight_report ?? ''),
      }))
    } else if (event.type === 'completed') {
      const hiddenTurns = parseHiddenTurnsFromRecord(event.data)
      const speakerSelections = parseSpeakerSelectionsFromRecord(event.data)
      isLiveRef.current = false
      setState((prev) => ({
        ...prev,
        isLive: false,
        terminationReason: (event.data.termination_reason as string | null) ?? null,
        statusText: 'Completed',
        hiddenTurns: hiddenTurns.length > 0 ? hiddenTurns : prev.hiddenTurns,
        speakerSelections:
          speakerSelections.length > 0 ? speakerSelections : prev.speakerSelections,
      }))
    } else if (event.type === 'status') {
      const turnIndex = event.data.turn_index as number
      setState((prev) => ({
        ...prev,
        statusText: `Turn ${turnIndex}`,
      }))
    } else if (event.type === 'error') {
      isLiveRef.current = false
      setState((prev) => ({
        ...prev,
        isLive: false,
        error: String(event.data.message ?? 'Simulation failed'),
      }))
    }
  }, [])

  const openStream = useCallback(() => {
    if (!meetingId) return

    disconnectRef.current?.()
    isLiveRef.current = true
    setState((prev) => ({ ...prev, isLive: true, error: null }))

    disconnectRef.current = streamMeeting(
      meetingId,
      handleStreamEvent,
      (err) => {
        isLiveRef.current = false
        setState((prev) => ({
          ...prev,
          isLive: false,
          error: err.message,
        }))
      },
    )
  }, [handleStreamEvent, meetingId])

  const connect = useCallback(() => {
    if (!meetingId) return
    reset()
    openStream()
  }, [meetingId, openStream, reset])

  const beginExtension = useCallback(
    (seed: ExtensionStreamSeed) => {
      if (!meetingId) return

      disconnectRef.current?.()
      isLiveRef.current = true
      setState({
        turns: [...seed.turns],
        hiddenTurns: [...seed.hiddenTurns],
        speakerSelections: [...seed.speakerSelections],
        workingProposals: [...seed.workingProposals],
        sharedFacts: [...seed.sharedFacts],
        insightReport: '',
        statusText: 'Đang mở rộng simulation…',
        terminationReason: null,
        isLive: true,
        error: null,
      })
      openStream()
    },
    [meetingId, openStream],
  )

  useEffect(() => {
    if (!meetingId || meetingStatus !== 'running') return
    if (isLiveRef.current) return
    connect()
  }, [connect, meetingId, meetingStatus])

  useEffect(() => {
    return () => disconnectRef.current?.()
  }, [])

  return { ...state, reconnect: connect, beginExtension, reset }
}
