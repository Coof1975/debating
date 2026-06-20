import type { LlmModelOption, LlmProviderOption } from '../types'

export const DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'
export const DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash'

export const DEFAULT_LLM_PROVIDERS: LlmProviderOption[] = [
  {
    id: 'openai',
    label: 'OpenAI',
    default_model: DEFAULT_OPENAI_MODEL,
    models: [{ id: 'gpt-4o-mini', label: 'GPT-4o Mini' }],
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    default_model: DEFAULT_GEMINI_MODEL,
    models: [{ id: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash' }],
  },
  {
    id: 'mock',
    label: 'Mock (dry-run)',
    default_model: 'mock',
    models: [{ id: 'mock', label: 'Mock responses' }],
  },
]

export function defaultModelForProvider(providerId: string): string {
  const provider = DEFAULT_LLM_PROVIDERS.find((p) => p.id === providerId)
  return provider?.default_model ?? DEFAULT_OPENAI_MODEL
}

export function modelOptionsWithCurrent(
  models: LlmModelOption[],
  currentModelId: string,
): LlmModelOption[] {
  if (!currentModelId || models.some((m) => m.id === currentModelId)) {
    return models
  }
  return [...models, { id: currentModelId, label: currentModelId }]
}
