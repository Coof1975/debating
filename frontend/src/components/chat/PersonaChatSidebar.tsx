import type { ChatSession } from '../../types'
import { roleColor } from '../../lib/utils'

type PersonaChatSidebarProps = {
  participantIds: string[]
  personaNames: Record<string, string>
  sessions: ChatSession[]
  activePersonaId: string | null
  onSelect: (personaId: string) => void
}

export function PersonaChatSidebar({
  participantIds,
  personaNames,
  sessions,
  activePersonaId,
  onSelect,
}: PersonaChatSidebarProps) {
  const sessionByPersona = new Map(sessions.map((s) => [s.persona_id, s]))

  return (
    <aside className="w-full shrink-0 lg:w-56">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Persona
      </p>
      <div className="space-y-1">
        {participantIds.map((role) => {
          const session = sessionByPersona.get(role)
          const isActive = activePersonaId === role
          const displayName = personaNames[role] || session?.persona_name || role
          return (
            <button
              key={role}
              type="button"
              onClick={() => onSelect(role)}
              className={`flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition ${
                isActive
                  ? 'bg-indigo-600/20 ring-1 ring-indigo-500/40'
                  : 'hover:bg-slate-800/60'
              }`}
            >
              <span
                className={`mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${roleColor(role)}`}
              >
                {role.slice(0, 2)}
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-medium text-white">{role}</span>
                <span className="block truncate text-xs text-slate-400">{displayName}</span>
                {session && session.message_count > 0 && (
                  <span className="mt-1 block truncate text-xs text-slate-500">
                    {session.message_count} tin · {session.last_message_preview}
                  </span>
                )}
              </span>
            </button>
          )
        })}
      </div>
    </aside>
  )
}
