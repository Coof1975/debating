export function InsightView({ insight, isLive }: { insight: string; isLive?: boolean }) {
  if (!insight && isLive) {
    return (
      <div className="card-padded bg-slate-900/60 text-sm text-slate-400">
        Insight report will appear when the meeting completes.
      </div>
    )
  }

  if (!insight) {
    return (
      <div className="card-padded border-dashed text-sm text-slate-500">
        No insight report yet.
      </div>
    )
  }

  return (
    <div className="card-padded border-indigo-500/30 bg-indigo-950/30">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-indigo-300">
        Insight report
      </h3>
      <div className="space-y-2 text-sm leading-relaxed whitespace-pre-wrap text-slate-200">
        {insight}
      </div>
    </div>
  )
}
