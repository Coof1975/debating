import { useCallback, useEffect, useRef, useState } from 'react'
import type { DialogueTurn } from '../types'
import { streamMeeting } from '../api/client'

type StreamState = {
  turns: DialogueTurn[]
  insightReport: string
  statusText: string
  terminationReason: string | null
  isLive: boolean
  error: string | null
}

export function useMeetingStream(meetingId: string | null, meetingStatus: string | undefined) {
  const [state, setState] = useState<StreamState>({
    turns: [],
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
        } else if (event.type === 'insight') {
          setState((prev) => ({
            ...prev,
            insightReport: String(event.data.insight_report ?? ''),
          }))
        } else if (event.type === 'completed') {
          setState((prev) => ({
            ...prev,
            isLive: false,
            terminationReason: (event.data.termination_reason as string | null) ?? null,
            statusText: 'Completed',
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
