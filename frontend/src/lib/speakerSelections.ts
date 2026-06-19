import type { SpeakerSelection } from '../types'

export function parseSpeakerSelections(raw: unknown): SpeakerSelection[] {
  if (!Array.isArray(raw)) return []
  return raw.filter(isSpeakerSelection)
}

function isSpeakerSelection(value: unknown): value is SpeakerSelection {
  if (!value || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    typeof item.next_speaker === 'string' &&
    typeof item.reason === 'string' &&
    typeof item.method === 'string' &&
    typeof item.turn_index === 'number'
  )
}

export function indexSpeakerSelections(
  selections: SpeakerSelection[],
): Map<number, SpeakerSelection> {
  const byTurn = new Map<number, SpeakerSelection>()
  for (const selection of selections) {
    byTurn.set(selection.turn_index, selection)
  }
  return byTurn
}
