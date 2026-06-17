type ParticipantChipsProps = {
  participantIds: string[]
  hostId?: string | null
}

export function ParticipantChips({ participantIds, hostId }: ParticipantChipsProps) {
  if (participantIds.length === 0) {
    return <p className="text-sm text-slate-500">No participants.</p>
  }

  return (
    <div className="flex flex-wrap gap-2">
      {participantIds.map((role) => {
        const isHost = role === hostId
        return (
          <span
            key={role}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm ${
              isHost
                ? 'bg-indigo-600/20 text-indigo-200 ring-1 ring-indigo-500/40'
                : 'bg-slate-800 text-slate-300 ring-1 ring-slate-700'
            }`}
          >
            {role}
            {isHost && (
              <span className="text-xs font-medium text-indigo-300">Chủ trì</span>
            )}
          </span>
        )
      })}
    </div>
  )
}
