import { Link } from 'react-router-dom'
import { MeetingEditForm } from '../../components/meeting/MeetingEditForm'
import { ParticipantChips } from '../../components/meeting/ParticipantChips'
import { RunSimulationButton } from '../../components/meeting/RunSimulationButton'
import { formatDate } from '../../lib/utils'
import { useMeetingHub } from './MeetingHubContext'

export function MeetingOverviewTab() {
  const {
    meetingId,
    meeting,
    isPending,
    isCompleted,
    isStreaming,
    starting,
    handleStart,
    displayError,
    setMeeting,
  } = useMeetingHub()

  return (
    <div className="section-gap">
      {displayError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {displayError}
        </div>
      )}

      {isPending && (
        <div className="card-padded border-indigo-500/30 bg-indigo-950/20">
          <h2 className="text-sm font-semibold text-indigo-200">
            Meeting đã tạo — chưa chạy simulation
          </h2>
          <p className="mt-2 text-sm text-slate-300">
            Kiểm tra thông tin bên dưới, sau đó chạy simulation để bắt đầu thảo luận giữa các
            persona.
          </p>
          <div className="mt-4">
            <RunSimulationButton onClick={handleStart} loading={starting} />
          </div>
        </div>
      )}

      {isStreaming && (
        <div className="card-padded border-sky-500/30 bg-sky-950/20">
          <h2 className="text-sm font-semibold text-sky-200">Simulation đang chạy</h2>
          <p className="mt-2 text-sm text-slate-300">
            Theo dõi transcript và insight report trên tab Simulation.
          </p>
          <Link
            to={`/meetings/${meetingId}/simulation`}
            className="mt-4 inline-block text-sm text-indigo-400 hover:text-indigo-300"
          >
            Mở tab Simulation →
          </Link>
        </div>
      )}

      {isCompleted && (
        <div className="card-padded border-emerald-500/30 bg-emerald-950/20">
          <h2 className="text-sm font-semibold text-emerald-200">Simulation đã hoàn thành</h2>
          <p className="mt-2 text-sm text-slate-300">
            Xem lại biên bản thảo luận và insight report, hoặc chat trực tiếp với persona.
          </p>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-3">
            <Link
              to={`/meetings/${meetingId}/simulation`}
              className="btn-secondary"
            >
              Xem simulation
            </Link>
            <Link
              to={`/meetings/${meetingId}/chat`}
              className="btn-primary border border-indigo-500/40 bg-indigo-950/40 text-indigo-100 hover:bg-indigo-900/50"
            >
              Chat với persona
            </Link>
          </div>
        </div>
      )}

      {meeting.status === 'failed' && (
        <div className="card-padded border-rose-500/30 bg-rose-950/20">
          <h2 className="text-sm font-semibold text-rose-200">Simulation thất bại</h2>
          {meeting.error_message && (
            <p className="mt-2 text-sm text-rose-100">{meeting.error_message}</p>
          )}
          <Link
            to={`/meetings/${meetingId}/simulation`}
            className="mt-4 inline-block text-sm text-indigo-400 hover:text-indigo-300"
          >
            Xem chi tiết trên tab Simulation →
          </Link>
        </div>
      )}

      <section className="card-padded bg-slate-900/40">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Thông tin meeting
        </h2>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">Chủ đề</dt>
            <dd className="mt-1 text-sm text-white">{meeting.topic}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Trạng thái</dt>
            <dd className="mt-1 text-sm text-slate-200">{meeting.status}</dd>
          </div>
          {meeting.scheduled_at && (
            <div>
              <dt className="text-xs text-slate-500">Lịch dự kiến</dt>
              <dd className="mt-1 text-sm text-slate-200">
                {formatDate(meeting.scheduled_at)}
              </dd>
            </div>
          )}
          {meeting.completed_at && (
            <div>
              <dt className="text-xs text-slate-500">Hoàn thành</dt>
              <dd className="mt-1 text-sm text-slate-200">
                {formatDate(meeting.completed_at)}
              </dd>
            </div>
          )}
          {Boolean(meeting.config?.llm_provider || meeting.config?.use_mock) && (
            <div>
              <dt className="text-xs text-slate-500">LLM</dt>
              <dd className="mt-1 text-sm text-slate-200">
                {meeting.config?.use_mock ? 'mock' : String(meeting.config?.llm_provider)} /{' '}
                {String(meeting.config?.llm_model ?? '')}
              </dd>
            </div>
          )}
        </dl>

        <div className="mt-6">
          <p className="text-xs text-slate-500">Thành phần tham dự</p>
          <div className="mt-2">
            <ParticipantChips
              participantIds={meeting.participant_ids}
              hostId={meeting.host_id}
            />
          </div>
        </div>

        {meeting.notes && (
          <div className="mt-6">
            <p className="text-xs text-slate-500">Ghi chú</p>
            <p className="mt-1 text-sm text-slate-200 whitespace-pre-wrap">{meeting.notes}</p>
          </div>
        )}

        {meeting.opening_message && (
          <div className="mt-6">
            <p className="text-xs text-slate-500">Lời mở đầu</p>
            <p className="mt-1 text-sm text-slate-200 whitespace-pre-wrap">
              {meeting.opening_message}
            </p>
          </div>
        )}

        {isPending && <MeetingEditForm meeting={meeting} onSaved={setMeeting} />}
      </section>
    </div>
  )
}
