export type DialogueTurn = {
  speaker_id: string
  speaker_name: string
  content: string
  round_number: number
  turn_index: number
}

export type InternalMonologue = {
  absorb: string
  compromise_space: string
  stance_shift: number
}

export type HiddenTurn = {
  speaker_id: string
  turn_index: number
  monologue: InternalMonologue
}

export type SpeakerSelectionMethod =
  | 'opening'
  | 'direct_request'
  | 'conflict_shortcut'
  | 'llm'
  | 'conflict_override'
  | 'heuristic_fallback'

export type SpeakerSelection = {
  next_speaker: string
  reason: string
  method: SpeakerSelectionMethod
  turn_index: number
}

export type ProposalApproval = {
  persona_id: string
  score: number
  concerns: string
}

export type WorkingProposal = {
  id: string
  author_id: string
  turn_index: number
  title: string
  description: string
  approvals: Record<string, ProposalApproval>
  aggregate_score: number
  status: string
  parent_id: string | null
}

export type SharedFact = {
  id: string
  source_speaker_id: string
  turn_index: number
  fact: string
  category: string
  confidence: number
  accepted_by: Record<string, boolean>
}

export type MeetingListItem = {
  id: string
  topic: string
  status: string
  participant_ids: string[]
  host_id: string | null
  scheduled_at: string | null
  termination_reason: string | null
  created_at: string
  completed_at: string | null
}

export type Meeting = {
  id: string
  topic: string
  opening_message: string
  notes: string
  host_id: string | null
  scheduled_at: string | null
  status: string
  participant_ids: string[]
  config: Record<string, unknown>
  record: {
    messages?: DialogueTurn[]
    metadata?: Record<string, unknown>
  } | null
  insight_report: string
  termination_reason: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
}

export type PersonaListItem = {
  role: string
  display_title: string
  name: string
  is_active: boolean
  updated_at: string
}

export type LlmModelOption = {
  id: string
  label: string
}

export type LlmProviderOption = {
  id: string
  label: string
  models: LlmModelOption[]
  default_model: string
}

export type StreamEvent = {
  type: string
  data: Record<string, unknown>
}

export type ChatSession = {
  id: string
  meeting_id: string
  persona_id: string
  persona_name: string
  message_count: number
  last_message_preview: string | null
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  session_id: string
  role: 'user' | 'assistant' | string
  content: string
  created_at: string
}

export type SendChatMessageResponse = {
  user_message: ChatMessage
  assistant_message: ChatMessage
}

export type CreateMeetingPayload = {
  topic: string
  opening_message?: string
  notes?: string
  scheduled_at?: string
  participant_ids: string[]
  host_id?: string
  max_turns?: number
  llm_provider: string
  llm_model?: string
  use_mock: boolean
  auto_start?: boolean
}

export type UpdateMeetingPayload = {
  topic?: string
  opening_message?: string
  notes?: string
  scheduled_at?: string | null
  participant_ids?: string[]
  host_id?: string
  max_turns?: number
  llm_provider?: string
  llm_model?: string
  use_mock?: boolean
}

export type PromptPreview = {
  role: string
  system_prompt: string
  meeting_topic: string | null
}

export type RebuildPromptsResult = {
  updated_personas: string[]
  message: string
}

export type SeedDatabaseResult = {
  status: string
  counts: Record<string, number>
}

export type RerunMeetingPayload = {
  llm_provider?: string
  llm_model?: string
  use_mock?: boolean
  max_turns?: number
}

export type PersonaSection = {
  key: string
  title: string
  content: string
}

export type PersonaRelationship = {
  target_role: string
  target_name: string
  stance: string
  behavior: string
}

export type NegotiationProfile = {
  compromise_threshold: number
  min_interest_retention: number
  director_sensitivity: number
  deadlock_tolerance: number
}

export type Persona = {
  role: string
  display_title: string
  name: string
  age: number | null
  tone_of_voice: string
  sections: Record<string, PersonaSection>
  relationships: PersonaRelationship[]
  llm_instructions: string
  negotiation?: NegotiationProfile | null
  is_active: boolean
  source_file: string
  system_prompt: string
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type PersonaCreatePayload = {
  role: string
  display_title: string
  name?: string
  age?: number | null
  tone_of_voice?: string
  sections?: Record<string, PersonaSection>
  relationships?: PersonaRelationship[]
  llm_instructions?: string
  negotiation?: NegotiationProfile | null
  is_active?: boolean
}

export type PersonaUpdatePayload = {
  display_title?: string
  name?: string
  age?: number | null
  tone_of_voice?: string
  sections?: Record<string, PersonaSection>
  relationships?: PersonaRelationship[]
  llm_instructions?: string
  negotiation?: NegotiationProfile | null
  is_active?: boolean
}

export type CompanySection = {
  key: string
  title: string
  content: string
  perspective: string
}

export type CompanyProfile = {
  company_name: string
  report_period: string
  source: string
  sections: Record<string, CompanySection>
  updated_at: string
}

export type CompanyProfileUpdatePayload = {
  company_name?: string
  report_period?: string
  source?: string
  sections?: Record<string, CompanySection>
}
