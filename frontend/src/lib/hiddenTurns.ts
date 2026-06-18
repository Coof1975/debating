import type { HiddenTurn, InternalMonologue } from '../types'

export function hiddenTurnKey(turn: { turn_index: number; speaker_id: string }): string {
  return `${turn.turn_index}-${turn.speaker_id}`
}

export function indexHiddenTurns(hiddenTurns: HiddenTurn[]): Map<string, HiddenTurn> {
  const map = new Map<string, HiddenTurn>()
  for (const hidden of hiddenTurns) {
    map.set(hiddenTurnKey(hidden), hidden)
  }
  return map
}

export function parseHiddenTurns(raw: unknown): HiddenTurn[] {
  if (!Array.isArray(raw)) return []
  return raw.filter((item): item is HiddenTurn => {
    if (!item || typeof item !== 'object') return false
    const record = item as Record<string, unknown>
    const monologue = record.monologue
    return (
      typeof record.speaker_id === 'string' &&
      typeof record.turn_index === 'number' &&
      !!monologue &&
      typeof monologue === 'object' &&
      typeof (monologue as InternalMonologue).absorb === 'string' &&
      typeof (monologue as InternalMonologue).compromise_space === 'string'
    )
  })
}

export function formatMonologue(monologue: InternalMonologue): string {
  const parts = [
    monologue.absorb.trim(),
    monologue.compromise_space.trim(),
  ].filter(Boolean)
  return parts.join('\n\n')
}

export function formatStanceShift(stanceShift: number): string | null {
  if (stanceShift === 0) return null
  const sign = stanceShift > 0 ? '+' : ''
  return `${sign}${stanceShift.toFixed(1)} flexibility`
}
