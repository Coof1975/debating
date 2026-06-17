import { Link } from 'react-router-dom'
import { InsightView } from '../../components/InsightView'
import { TranscriptView } from '../../components/TranscriptView'
import { canAccessSimulationTab, useMeetingHub } from './MeetingHubContext'

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
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Conversation
          </h2>
          <TranscriptView turns={turns} isLive={isStreaming && stream.isLive} />
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
