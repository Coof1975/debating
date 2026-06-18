import type { DialogueTurn, HiddenTurn } from '../types'
import {
  formatMonologue,
  formatStanceShift,
  hiddenTurnKey,
  indexHiddenTurns,
} from '../lib/hiddenTurns'
import { roleColor } from '../lib/utils'

export function TranscriptView({
  turns,
  hiddenTurns = [],
  showInternalReasoning = true,
  isLive,
}: {
  turns: DialogueTurn[]
  hiddenTurns?: HiddenTurn[]
  showInternalReasoning?: boolean
  isLive?: boolean
}) {
  const hiddenByKey = indexHiddenTurns(hiddenTurns)

  if (turns.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-dashed border-slate-700 text-slate-400">
        {isLive ? 'Waiting for first turn…' : 'No conversation yet.'}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {turns.map((turn) => {
        const hidden = hiddenByKey.get(hiddenTurnKey(turn))
        const monologue = hidden?.monologue
        const stanceLabel = monologue ? formatStanceShift(monologue.stance_shift) : null

        return (
          <article
            key={`${turn.turn_index}-${turn.speaker_id}`}
            className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
          >
            <div className="mb-2 flex items-center gap-3">
              <span
                className={`rounded-md px-2 py-0.5 text-xs font-bold text-white ${roleColor(turn.speaker_id)}`}
              >
                {turn.speaker_id}
              </span>
              <span className="text-sm font-medium text-slate-200">{turn.speaker_name}</span>
              <span className="text-xs text-slate-500">
                Turn {turn.turn_index} · Round {turn.round_number}
              </span>
            </div>

            {showInternalReasoning && monologue && (
              <div className="mb-3 rounded-lg border border-slate-800/80 bg-slate-950/50 px-3 py-2">
                <div className="mb-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-slate-500">
                  <span>Internal reasoning</span>
                  {stanceLabel && (
                    <span className="normal-case tracking-normal text-slate-600">{stanceLabel}</span>
                  )}
                </div>
                <p className="whitespace-pre-wrap text-sm italic leading-relaxed text-slate-400">
                  {formatMonologue(monologue)}
                </p>
              </div>
            )}

            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
              {turn.content}
            </p>
          </article>
        )
      })}
      {isLive && (
        <div className="flex items-center gap-2 text-sm text-sky-400">
          <span className="h-2 w-2 animate-pulse rounded-full bg-sky-400" />
          Simulation in progress…
        </div>
      )}
    </div>
  )
}
