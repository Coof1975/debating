import { useCallback, useEffect, useRef, useState } from 'react'
import { parseHiddenTurns } from '../lib/hiddenTurns'
import type { DialogueTurn, HiddenTurn, SharedFact, WorkingProposal } from '../types'
import { streamMeeting } from '../api/client'

type StreamState = {
  turns: DialogueTurn[]
  hiddenTurns: HiddenTurn[]
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

export function useMeetingStream(meetingId: string | null, meetingStatus: string | undefined) {
  const [state, setState] = useState<StreamState>({
    turns: [],
    hiddenTurns: [],
    workingProposals: [],
    sharedFacts: [],
    insightReport: '',
    statusText: '',
    terminationReason: null,
    isLive: false,
    error: null,
  })
  const disconnectRef = useRef<(() => void) | null>(null)

  const reset = useCallback(() => {
    setState({
      turns: [],
      hiddenTurns: [],
      workingProposals: [],
      sharedFacts: [],
      insightReport: '',
      statusText: '',
      terminationReason: null,
      isLive: false,
      error: null,
    })
  }, [])

  const connect = useCallback(() => {
    if (!meetingId) return

    disconnectRef.current?.()
    reset()
    setState((prev) => ({ ...prev, isLive: true }))

    disconnectRef.current = streamMeeting(
      meetingId,
      (event) => {
        if (event.type === 'turn') {
          const turn = event.data as DialogueTurn
          setState((prev) => ({
            ...prev,
            turns: [...prev.turns, turn],
            statusText: `Turn ${turn.turn_index}`,
          }))
        } else if (event.type === 'monologue') {
          const hidden = parseHiddenTurnEvent(event.data)
          if (!hidden) return
          setState((prev) => ({
            ...prev,
            hiddenTurns: [...prev.hiddenTurns, hidden],
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
          setState((prev) => ({
            ...prev,
            isLive: false,
            terminationReason: (event.data.termination_reason as string | null) ?? null,
            statusText: 'Completed',
            hiddenTurns: hiddenTurns.length > 0 ? hiddenTurns : prev.hiddenTurns,
          }))
        } else if (event.type === 'status') {
          const turnIndex = event.data.turn_index as number
          setState((prev) => ({
            ...prev,
            statusText: `Turn ${turnIndex}`,
          }))
        } else if (event.type === 'error') {
          setState((prev) => ({
            ...prev,
            isLive: false,
            error: String(event.data.message ?? 'Simulation failed'),
          }))
        }
      },
      (err) => {
        setState((prev) => ({
          ...prev,
          isLive: false,
          error: err.message,
        }))
      },
    )
  }, [meetingId, reset])

  useEffect(() => {
    if (!meetingId) return

    const shouldStream =
      meetingStatus === 'running' ||
      meetingStatus === 'completed' ||
      meetingStatus === 'failed'

    if (shouldStream) {
      connect()
    }

    return () => disconnectRef.current?.()
  }, [meetingId, meetingStatus, connect])

  return { ...state, reconnect: connect, reset }
}
