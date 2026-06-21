import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { FacilitatorComposer } from '../../components/meeting/FacilitatorComposer'
import { ExtensionRejectedBanner } from '../../components/meeting/ExtensionRejectedBanner'
import { InsightView } from '../../components/InsightView'
import { TranscriptView } from '../../components/TranscriptView'
import {
  buildFollowUpMeetingPrefill,
  extractNextStepsSection,
} from '../../lib/insightFollowUp'
import { defaultModelForProvider, modelOptionsWithCurrent } from '../../lib/llmOptions'
import type { SharedFact } from '../../types'
import type { NewMeetingLocationState } from '../../types/navigation'
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
    showOrchestratorDecisions,
    setShowOrchestratorDecisions,
    speakerSelections,
    workingProposals,
    sharedFacts,
    insight,
    displayError,
    rerunning,
    showRerun,
    setShowRerun,
    handleRerun,
    extending,
    extensionRejection,
    pendingExtensionContent,
    handleExtend,
    handleEvaluateExtension,
    dismissExtensionRejection,
  } = useMeetingHub()

  const nextStepsSection = useMemo(() => extractNextStepsSection(insight), [insight])
  const followUpNavigation = useMemo((): NewMeetingLocationState | null => {
    if (!nextStepsSection || meeting.status !== 'completed') return null
    return {
      followUpFrom: {
        meetingId,
        priorTopic: meeting.topic,
      },
      prefill: buildFollowUpMeetingPrefill({
        meetingId,
        priorTopic: meeting.topic,
        nextSteps: nextStepsSection,
        participantIds: meeting.participant_ids,
        hostId: meeting.host_id,
      }),
    }
  }, [meeting, meetingId, nextStepsSection])

  if (!canAccessSimulationTab(meeting.status)) {
    return (
      <div className="card-padded border-dashed p-8 text-center sm:p-10">
        <p className="text-sm text-slate-400">Simulation chưa được chạy.</p>
        <Link
          to={`/meetings/${meetingId}/overview`}
          className="btn-secondary mt-4 inline-flex text-sm"
        >
          ← Quay lại Tổng quan
        </Link>
      </div>
    )
  }

  return (
    <div className="section-gap">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex flex-col gap-1 text-xs text-slate-500 sm:flex-row sm:flex-wrap sm:gap-x-4">
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
            className="btn-secondary w-full sm:w-auto"
          >
            Rerun simulation
          </button>
        )}
      </div>

      {showRerun && (
        <div className="card-padded bg-slate-900/80">
          <p className="text-sm text-slate-300">
            Thao tác này sẽ xóa transcript và insight hiện tại, rồi chạy simulation mới với
            cùng chủ đề: <span className="text-white">{meeting.topic}</span>
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <select
              value={providerId}
              onChange={(e) => {
                const nextProviderId = e.target.value
                setProviderId(nextProviderId)
                setModelId(defaultModelForProvider(nextProviderId, providers))
              }}
              className="input-field"
            >
              {providers.map((p) => (
                <option key={p.id} value={p.id}>{p.label}</option>
              ))}
            </select>
            <select
              value={modelId}
              onChange={(e) => setModelId(e.target.value)}
              className="input-field"
            >
              {(modelOptionsWithCurrent(activeProvider?.models ?? [], modelId)).map((m) => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
          </div>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:gap-3">
            <button
              type="button"
              onClick={handleRerun}
              disabled={rerunning || meeting.status === 'running'}
              className="btn-primary"
            >
              {rerunning ? 'Đang chạy lại…' : 'Xác nhận rerun'}
            </button>
            <button
              type="button"
              onClick={() => setShowRerun(false)}
              className="btn-secondary"
            >
              Hủy
            </button>
          </div>
        </div>
      )}

      {displayError && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {displayError}
        </div>
      )}

      {extensionRejection && (
        <ExtensionRejectedBanner
          meetingId={meetingId}
          rejection={extensionRejection}
          pendingContent={pendingExtensionContent}
          onForceContinue={() => handleExtend(pendingExtensionContent, true)}
          onDismiss={dismissExtensionRejection}
          forcing={extending}
        />
      )}

      {meeting.status === 'completed' && (
        <FacilitatorComposer
          onSend={handleExtend}
          onEvaluate={handleEvaluateExtension}
          disabled={extending}
          sending={extending}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div>
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
                Conversation
              </h2>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
                <label className="flex min-h-10 cursor-pointer items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    checked={showOrchestratorDecisions}
                    onChange={(e) => setShowOrchestratorDecisions(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-500/40"
                  />
                  Show orchestrator decisions
                </label>
                <label className="flex min-h-10 cursor-pointer items-center gap-2 text-xs text-slate-400">
                  <input
                    type="checkbox"
                    checked={showInternalReasoning}
                    onChange={(e) => setShowInternalReasoning(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-600 bg-slate-900 text-indigo-500 focus:ring-indigo-500/40"
                  />
                  Show internal reasoning
                </label>
              </div>
            </div>
            <TranscriptView
              turns={turns}
              hiddenTurns={hiddenTurns}
              speakerSelections={speakerSelections}
              showInternalReasoning={showInternalReasoning}
              showOrchestratorDecisions={showOrchestratorDecisions}
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
                    <li key={proposal.id} className="card-padded bg-slate-900/60 text-sm">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <p className="font-medium text-slate-100">{proposal.title}</p>
                        <span className="shrink-0 self-start rounded bg-indigo-950 px-2 py-0.5 text-xs text-indigo-300">
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
                    <li key={fact.id} className="card-padded bg-slate-900/60 text-sm">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <p className="font-medium text-slate-100">{fact.fact}</p>
                        <span
                          className={`shrink-0 self-start rounded px-2 py-0.5 text-xs capitalize ${
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
                      <p className="mt-1 break-words text-xs text-slate-600">
                        {formatAcceptances(fact)}
                      </p>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
        <div>
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Analysis
            </h2>
            {followUpNavigation && (
              <Link
                to="/meetings/new"
                state={followUpNavigation}
                className="btn-secondary w-full text-center text-xs sm:w-auto"
              >
                Tạo meeting tiếp theo
              </Link>
            )}
          </div>
          <InsightView
            insight={insight}
            isLive={isStreaming && !insight && !stream.error}
          />
        </div>
      </div>

      {meeting.status === 'completed' && (
        <div className="card-padded text-sm text-slate-400">
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
