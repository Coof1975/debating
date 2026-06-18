import { Link } from 'react-router-dom'
import { InsightView } from '../../components/InsightView'
import { TranscriptView } from '../../components/TranscriptView'
import type { SharedFact } from '../../types'
import { canAccessSimulationTab, useMeetingHub } from './MeetingHubContext'

const CATEGORY_STYLES: Record<string, string> = {
  financial: 'bg-emerald-950 text-emerald-300',
  operational: 'bg-amber-950 text-amber-300',
  market: 'bg-sky-950 text-sky-300',
  other: 'bg-slate-800 text-slate-300',
}

function formatAcceptances(fact: SharedFact): string {
  const entries = Object.entries(fact.accepted_by ?? {})
  if (entries.length === 0) return 'No responses yet'
  return entries
    .map(([personaId, accepted]) => `${personaId}: ${accepted ? 'accepted' : 'rejected'}`)
    .join(' · ')
}

export function MeetingSimulationTab() {
  const {
    meetingId,
    meeting,
    providers,
    providerId,
    setProviderId,
    modelId,
    setModelId,
    activeProvider,
    isStreaming,
    stream,
    turns,
    hiddenTurns,
    showInternalReasoning,
    setShowInternalReasoning,
    workingProposals,
    sharedFacts,
    insight,
    displayError,
    rerunning,
    showRerun,
    setShowRerun,
    handleRerun,
  } = useMeetingHub()

  if (!canAccessSimulationTab(meeting.status)) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center">
        <p className="text-slate-400">Simulation chưa được chạy.</p>
        <Link
          to={`/meetings/${meetingId}/overview`}
          className="mt-4 inline-block text-sm text-indigo-400 hover:text-indigo-300"
        >
          ← Quay lại Tổng quan để chạy simulation
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-4 text-xs text-slate-500">
          {Boolean(meeting.config?.llm_provider || meeting.config?.use_mock) && (
            <span>
              LLM: {meeting.config?.use_mock ? 'mock' : String(meeting.config?.llm_provider)} /{' '}
              {String(meeting.config?.llm_model ?? '')}
            </span>
          )}
          {meeting.termination_reason && <span>Ended: {meeting.termination_reason}</span>}
          {isStreaming && stream.statusText && <span>{stream.statusText}</span>}
        </div>
        {meeting.status !== 'running' && (
          <button
            type="button"
            onClick={() => setShowRerun(!showRerun)}
            className="rounded-lg border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
          >
            Rerun simulation
          </button>
        )}
      </div>

      {showRerun && (
        <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
          <p className="text-sm text-slate-300">
            Thao tác này sẽ xóa transcript và insight hiện tại, rồi chạy simulation mới với
            cùng chủ đề: <span className="text-white">{meeting.topic}</span>
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <select
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <select
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-white"
            >
              {(activeProvider?.models ?? []).map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={handleRerun}
              disabled={rerunning || meeting.status === 'running'}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
            >
              {rerunning ? 'Đang chạy lại…' : 'Xác nhận rerun'}
            </button>
            <button
              type="button"
              onClick={() => setShowRerun(false)}
              className="text-sm text-slate-400 hover:text-white"
            >
              Hủy
            </button>
          </div>
        </div>
      )}

      {displayError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {displayError}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                Conversation
              </h2>
              <label className="flex cursor-pointer items-center gap-2 text-xs text-slate-400">
                <input
                  type="checkbox"
                  checked={showInternalReasoning}
                  onChange={(e) => setShowInternalReasoning(e.target.checked)}
                  className="rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-500/40"
                />
                Show internal reasoning
              </label>
            </div>
            <TranscriptView
              turns={turns}
              hiddenTurns={hiddenTurns}
              showInternalReasoning={showInternalReasoning}
              isLive={isStreaming && stream.isLive}
            />
          </div>
          {workingProposals.length > 0 && (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Working proposals
              </h2>
              <ul className="space-y-3">
                {workingProposals
                  .filter((p) => p.status === 'active')
                  .sort((a, b) => b.aggregate_score - a.aggregate_score)
                  .map((proposal) => (
                    <li
                      key={proposal.id}
                      className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 text-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-slate-100">{proposal.title}</p>
                        <span className="shrink-0 rounded bg-indigo-950 px-2 py-0.5 text-xs text-indigo-300">
                          {Math.round(proposal.aggregate_score * 100)}%
                        </span>
                      </div>
                      <p className="mt-1 text-slate-400">{proposal.description}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        {proposal.author_id} · turn {proposal.turn_index}
                      </p>
                    </li>
                  ))}
              </ul>
            </div>
          )}
          {sharedFacts.length > 0 && (
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                Shared facts
              </h2>
              <ul className="space-y-3">
                {[...sharedFacts]
                  .sort((a, b) => b.turn_index - a.turn_index)
                  .map((fact) => (
                    <li
                      key={fact.id}
                      className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 text-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-slate-100">{fact.fact}</p>
                        <span
                          className={`shrink-0 rounded px-2 py-0.5 text-xs capitalize ${
                            CATEGORY_STYLES[fact.category] ?? CATEGORY_STYLES.other
                          }`}
                        >
                          {fact.category}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        {fact.source_speaker_id} · turn {fact.turn_index} ·{' '}
                        {Math.round(fact.confidence * 100)}% confidence
                      </p>
                      <p className="mt-1 text-xs text-slate-600">{formatAcceptances(fact)}</p>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Analysis
          </h2>
          <InsightView insight={insight} isLive={isStreaming && stream.isLive} />
        </div>
      </div>

      {meeting.status === 'completed' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">
          Muốn hỏi thêm persona về cuộc họp?{' '}
          <Link
            to={`/meetings/${meetingId}/chat`}
            className="text-indigo-400 hover:text-indigo-300"
          >
            Mở tab Chat →
          </Link>
        </div>
      )}
    </div>
  )
}
