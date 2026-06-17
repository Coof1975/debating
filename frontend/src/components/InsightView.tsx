export function InsightView({ insight, isLive }: { insight: string; isLive?: boolean }) {
  if (!insight && isLive) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 text-sm text-slate-400">
        Insight report will appear when the meeting completes.
      </div>
    )
  }

  if (!insight) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 p-6 text-sm text-slate-500">
        No insight report yet.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-indigo-500/30 bg-indigo-950/30 p-6">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-indigo-300">
        Insight report
      </h3>
      <div className="space-y-2 text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
        {insight}
      </div>
    </div>
  )
}
