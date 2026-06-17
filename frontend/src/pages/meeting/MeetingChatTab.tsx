import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import { ChatComposer } from '../../components/chat/ChatComposer'
import { ChatMessageList } from '../../components/chat/ChatMessageList'
import { PersonaChatSidebar } from '../../components/chat/PersonaChatSidebar'
import { useChatSession } from '../../hooks/useChatSession'
import type { ChatSession } from '../../types'
import { canAccessChatTab, useMeetingHub } from './MeetingHubContext'

export function MeetingChatTab() {
  const { meetingId, meeting } = useMeetingHub()
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activePersonaId, setActivePersonaId] = useState<string | null>(null)
  const [personaNames, setPersonaNames] = useState<Record<string, string>>({})

  const chat = useChatSession(meetingId, activePersonaId)

  useEffect(() => {
    if (!canAccessChatTab(meeting.status)) return
    api.listChatSessions(meetingId).then(setSessions).catch(() => setSessions([]))
    api.listPersonas().then((rows) => {
      const names: Record<string, string> = {}
      for (const row of rows) {
        names[row.role] = row.name || row.display_title
      }
      setPersonaNames(names)
    })
  }, [meetingId, meeting.status, activePersonaId, chat.session?.id, chat.session?.updated_at])

  useEffect(() => {
    if (activePersonaId) return
    const first = meeting.participant_ids[0]
    if (first) setActivePersonaId(first)
  }, [activePersonaId, meeting.participant_ids])

  const activePersonaName = useMemo(() => {
    if (!activePersonaId) return ''
    return (
      personaNames[activePersonaId] ||
      chat.session?.persona_name ||
      activePersonaId
    )
  }, [activePersonaId, personaNames, chat.session?.persona_name])

  if (!canAccessChatTab(meeting.status)) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 p-10 text-center">
        <p className="text-slate-400">
          {meeting.status === 'running'
            ? 'Đợi simulation hoàn thành trước khi chat với persona.'
            : 'Cần hoàn thành simulation trước khi chat với persona.'}
        </p>
        <Link
          to={`/meetings/${meetingId}/overview`}
          className="mt-4 inline-block text-sm text-indigo-400 hover:text-indigo-300"
        >
          ← Quay lại Tổng quan
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900/30 p-4 text-sm text-slate-400">
        Chat riêng 1-1 sau cuộc họp <span className="text-white">{meeting.topic}</span>.
        Persona trả lời dựa trên biên bản simulation và tính cách nhân vật.
      </div>

      <div className="flex min-h-[480px] flex-col gap-6 lg:flex-row">
        <PersonaChatSidebar
          participantIds={meeting.participant_ids}
          personaNames={personaNames}
          sessions={sessions}
          activePersonaId={activePersonaId}
          onSelect={setActivePersonaId}
        />

        <div className="flex min-w-0 flex-1 flex-col rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          <div className="mb-4 flex items-center justify-between gap-3 border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-semibold text-white">
                {activePersonaId ?? 'Chọn persona'}
              </h2>
              {activePersonaName && (
                <p className="text-xs text-slate-400">{activePersonaName}</p>
              )}
            </div>
            <Link
              to={`/meetings/${meetingId}/simulation`}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              Xem transcript
            </Link>
          </div>

          <div className="flex-1 overflow-y-auto pr-1">
            {chat.error && (
              <div className="mb-4 rounded-lg border border-rose-500/40 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
                {chat.error}
              </div>
            )}
            <ChatMessageList
              messages={chat.messages}
              personaName={activePersonaName}
              personaId={activePersonaId ?? ''}
              loading={chat.loading}
            />
          </div>

          <ChatComposer
            onSend={chat.sendMessage}
            disabled={!activePersonaId || chat.loading}
            sending={chat.sending}
          />
        </div>
      </div>
    </div>
  )
}
