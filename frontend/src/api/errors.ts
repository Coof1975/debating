import { parseExtensionRejectedDetail } from '../lib/meetingExtension'
import type { ExtensionRejectedDetail } from '../types'

export class ApiRequestError extends Error {
  status: number
  detail: unknown

  constructor(message: string, status: number, detail?: unknown) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.detail = detail
  }
}

export function getExtensionRejected(error: unknown): ExtensionRejectedDetail | null {
  if (!(error instanceof ApiRequestError) || error.status !== 409) {
    return null
  }
  return parseExtensionRejectedDetail(error.detail)
}
