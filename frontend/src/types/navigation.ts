import type { FollowUpMeetingPrefill } from '../lib/insightFollowUp'

export type NewMeetingLocationState = {
  followUpFrom?: {
    meetingId: string
    priorTopic: string
  }
  prefill?: FollowUpMeetingPrefill
}
