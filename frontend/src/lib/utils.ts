const ROLE_COLORS: Record<string, string> = {
  CEO: 'bg-blue-600',
  CFO: 'bg-emerald-600',
  MARKETING: 'bg-pink-600',
  PRODUCT: 'bg-amber-600',
  SALE: 'bg-violet-600',
}

export function roleColor(role: string): string {
  return ROLE_COLORS[role] ?? 'bg-slate-600'
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

export function statusLabel(status: string): string {
  switch (status) {
    case 'pending':
      return 'Pending'
    case 'running':
      return 'Running'
    case 'completed':
      return 'Completed'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

export function statusClasses(status: string): string {
  switch (status) {
    case 'running':
      return 'bg-sky-500/20 text-sky-300 ring-sky-500/40'
    case 'completed':
      return 'bg-emerald-500/20 text-emerald-300 ring-emerald-500/40'
    case 'failed':
      return 'bg-rose-500/20 text-rose-300 ring-rose-500/40'
    default:
      return 'bg-slate-500/20 text-slate-300 ring-slate-500/40'
  }
}
