import { parseHiddenTurns } from './hiddenTurns'
import { parseSpeakerSelections } from './speakerSelections'
import type {
  DialogueTurn,
  ExtensionRejectedDetail,
  HiddenTurn,
  Meeting,
  SharedFact,
  SpeakerSelection,
  WorkingProposal,
} from '../types'

export const FACILITATOR_SPEAKER_ID = 'FACILITATOR'

export type ExtensionStreamSeed = {
  turns: DialogueTurn[]
  hiddenTurns: HiddenTurn[]
  speakerSelections: SpeakerSelection[]
  workingProposals: WorkingProposal[]
  sharedFacts: SharedFact[]
}

export function buildExtensionStreamSeed(meeting: Meeting): ExtensionStreamSeed {
  const metadata = meeting.record?.metadata ?? {}
  return {
    turns: [...(meeting.record?.messages ?? [])],
    hiddenTurns: parseHiddenTurns(metadata.hidden_turns),
    speakerSelections: parseSpeakerSelections(metadata.speaker_selections),
    workingProposals: (metadata.working_proposals as WorkingProposal[] | undefined) ?? [],
    sharedFacts: (metadata.shared_facts as SharedFact[] | undefined) ?? [],
  }
}

export function parseExtensionRejectedDetail(detail: unknown): ExtensionRejectedDetail | null {
  if (!detail || typeof detail !== 'object') return null
  const payload = detail as Record<string, unknown>
  if (payload.accepted !== false) return null
  return {
    accepted: false,
    reason: String(payload.reason ?? 'Tin nhắn chưa đủ ý nghĩa.'),
    suggestion: String(payload.suggestion ?? 'none'),
  }
}

export function extensionSuggestionLabel(suggestion: string): string {
  switch (suggestion) {
    case 'chat_with_persona':
      return 'Thử chat riêng với persona trên tab Chat.'
    case 'extend':
      return 'Có thể mở lại cuộc họp nhóm.'
    default:
      return 'Không cần hành động thêm.'
  }
}
