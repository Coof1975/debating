import { Link } from 'react-router-dom'
import { AppHeader } from './AppHeader'

export function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <AppHeader zone="workspace" />
      <div className="border-b border-slate-800/60 bg-slate-950/40">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3 text-sm">
          <Link to="/" className="text-slate-300 hover:text-white">
            Meetings
          </Link>
          <Link
            to="/meetings/new"
            className="rounded-lg bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-500"
          >
            New meeting
          </Link>
        </div>
      </div>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </div>
  )
}
