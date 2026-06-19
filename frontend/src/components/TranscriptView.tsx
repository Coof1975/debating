import type { DialogueTurn, HiddenTurn, SpeakerSelection } from '../types'
import { FACILITATOR_SPEAKER_ID } from '../lib/meetingExtension'
import {
  formatMonologue,
  formatStanceShift,
  hiddenTurnKey,
  indexHiddenTurns,
} from '../lib/hiddenTurns'
import { indexSpeakerSelections } from '../lib/speakerSelections'
import { roleColor } from '../lib/utils'

const METHOD_LABELS: Record<SpeakerSelection['method'], string> = {
  opening: 'opening',
  direct_request: 'direct request',
  conflict_shortcut: 'conflict shortcut',
  llm: 'llm',
  conflict_override: 'conflict override',
  heuristic_fallback: 'heuristic',
  facilitator_directive: 'facilitator directive',
}

export function TranscriptView({
  turns,
  hiddenTurns = [],
  speakerSelections = [],
  showInternalReasoning = true,
  showOrchestratorDecisions = false,
  isLive,
}: {
  turns: DialogueTurn[]
  hiddenTurns?: HiddenTurn[]
  speakerSelections?: SpeakerSelection[]
  showInternalReasoning?: boolean
  showOrchestratorDecisions?: boolean
  isLive?: boolean
}) {
  const hiddenByKey = indexHiddenTurns(hiddenTurns)
  const selectionByTurn = indexSpeakerSelections(speakerSelections)

  if (turns.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-400 sm:h-64">
        {isLive ? 'Waiting for first turn…' : 'No conversation yet.'}
      </div>
    )
  }

  return (
    <div className="space-y-3 sm:space-y-4">
      {turns.map((turn) => {
        const hidden = hiddenByKey.get(hiddenTurnKey(turn))
        const monologue = hidden?.monologue
        const stanceLabel = monologue ? formatStanceShift(monologue.stance_shift) : null
        const selection = selectionByTurn.get(turn.turn_index)
        const isFacilitator = turn.speaker_id === FACILITATOR_SPEAKER_ID

        return (
          <article
            key={`${turn.turn_index}-${turn.speaker_id}`}
            className={
              isFacilitator
                ? 'card-padded border border-amber-500/35 bg-amber-950/25'
                : 'card-padded bg-slate-900/60'
            }
          >
            {showOrchestratorDecisions && selection && !isFacilitator && (
              <div className="mb-3 rounded-xl border border-violet-900/50 bg-violet-950/20 px-3 py-2.5">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-violet-400/80">
                  <span>Orchestrator</span>
                  <span className="normal-case tracking-normal text-violet-300/70">
                    → {selection.next_speaker}
                  </span>
                  <span className="rounded bg-violet-950/80 px-1.5 py-0.5 text-[10px] normal-case tracking-normal text-violet-400/60">
                    {METHOD_LABELS[selection.method] ?? selection.method}
                  </span>
                </div>
                <p className="text-sm leading-relaxed text-violet-200/80">{selection.reason}</p>
              </div>
            )}

            <div className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              <span
                className={`rounded-md px-2 py-0.5 text-xs font-bold text-white ${roleColor(turn.speaker_id)}`}
              >
                {isFacilitator ? 'FACILITATOR' : turn.speaker_id}
              </span>
              <span className={`text-sm font-medium ${isFacilitator ? 'text-amber-100' : 'text-slate-200'}`}>
                {turn.speaker_name}
              </span>
              {isFacilitator && (
                <span className="rounded bg-amber-900/60 px-2 py-0.5 text-[10px] uppercase tracking-wide text-amber-200/80">
                  Người tổ chức
                </span>
              )}
              <span className="text-xs text-slate-500">
                Turn {turn.turn_index} · Round {turn.round_number}
              </span>
            </div>

            {showInternalReasoning && monologue && !isFacilitator && (
              <div className="mb-3 rounded-xl border border-slate-800/80 bg-slate-950/50 px-3 py-2.5">
                <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-wide text-slate-500">
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

            <p className={`whitespace-pre-wrap text-sm leading-relaxed ${isFacilitator ? 'text-amber-50/95' : 'text-slate-300'}`}>
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
