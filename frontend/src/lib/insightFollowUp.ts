export type FollowUpMeetingPrefill = {
  topic: string
  notes: string
  openingMessage?: string
  participantIds: string[]
  hostId: string
}

const SECTION_HEADER =
  /(?:^|\n)(?:#{1,3}\s*)?7\.\s*Đề xuất bước tiếp theo\s*(?:\n|$)/i

/** Extract section 7 content from an insight report, if present. */
export function extractNextStepsSection(insight: string): string | null {
  const trimmed = insight.trim()
  if (!trimmed) return null

  const headerMatch = trimmed.match(SECTION_HEADER)
  if (!headerMatch || headerMatch.index === undefined) return null

  const start = headerMatch.index + headerMatch[0].length
  const rest = trimmed.slice(start)
  const nextSection = rest.search(/\n(?:#{1,3}\s*)?\d+\.\s+/m)
  const body = (nextSection >= 0 ? rest.slice(0, nextSection) : rest).trim()

  return body || null
}

function cleanBulletLine(line: string): string {
  return line.replace(/^[-*•]\s*/, '').replace(/^\d+[.)]\s*/, '').trim()
}

/** Pick a concise meeting topic from the next-steps section. */
export function deriveTopicFromNextSteps(section: string): string {
  const lines = section
    .split('\n')
    .map((line) => cleanBulletLine(line.trim()))
    .filter(Boolean)

  for (const line of lines) {
    if (line.length >= 10) {
      if (line.length <= 140) return line
      const truncated = line.slice(0, 140)
      const lastSpace = truncated.lastIndexOf(' ')
      return `${lastSpace > 80 ? truncated.slice(0, lastSpace) : truncated}…`
    }
  }

  const fallback = lines[0] ?? 'Cuộc họp tiếp theo'
  return fallback.length <= 140 ? fallback : `${fallback.slice(0, 137)}…`
}

export function buildFollowUpMeetingPrefill(input: {
  meetingId: string
  priorTopic: string
  nextSteps: string
  participantIds: string[]
  hostId: string | null
}): FollowUpMeetingPrefill {
  const topic = deriveTopicFromNextSteps(input.nextSteps)
  const notes = [
    `Tiếp nội dung cuộc họp: "${input.priorTopic}"`,
    `(Meeting ID: ${input.meetingId})`,
    '',
    'Đề xuất bước tiếp theo (từ insight report):',
    input.nextSteps,
  ].join('\n')

  const hostId =
    input.hostId && input.participantIds.includes(input.hostId)
      ? input.hostId
      : input.participantIds.includes('CEO')
        ? 'CEO'
        : (input.participantIds[0] ?? '')

  return {
    topic,
    notes,
    participantIds: [...input.participantIds],
    hostId,
  }
}
