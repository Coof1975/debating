import { createContext, useContext } from 'react'
import type { useMeetingStream } from '../../hooks/useMeetingStream'
import type { DialogueTurn, LlmProviderOption, Meeting } from '../../types'

export type MeetingHubContextValue = {
  meetingId: string
  meeting: Meeting
  setMeeting: (meeting: Meeting) => void
  loadMeeting: () => Promise<void>
  error: string | null
  setError: (error: string | null) => void
  providers: LlmProviderOption[]
  providerId: string
  setProviderId: (id: string) => void
  modelId: string
  setModelId: (id: string) => void
  activeProvider: LlmProviderOption | undefined
  isPending: boolean
  isStreaming: boolean
  isCompleted: boolean
  stream: ReturnType<typeof useMeetingStream>
  turns: DialogueTurn[]
  insight: string
  displayError: string | null
  starting: boolean
  handleStart: () => Promise<void>
  rerunning: boolean
  showRerun: boolean
  setShowRerun: (show: boolean) => void
  handleRerun: () => Promise<void>
  deleting: boolean
  handleDelete: () => Promise<void>
}

const MeetingHubContext = createContext<MeetingHubContextValue | null>(null)

export function MeetingHubProvider({
  value,
  children,
}: {
  value: MeetingHubContextValue
  children: React.ReactNode
}) {
  return <MeetingHubContext.Provider value={value}>{children}</MeetingHubContext.Provider>
}

export function useMeetingHub(): MeetingHubContextValue {
  const ctx = useContext(MeetingHubContext)
  if (!ctx) {
    throw new Error('useMeetingHub must be used within MeetingHubProvider')
  }
  return ctx
}

export function canAccessSimulationTab(status: string): boolean {
  return status === 'running' || status === 'completed' || status === 'failed'
}

export function canAccessChatTab(status: string): boolean {
  return status === 'completed'
}
