import { Link, useLocation } from 'react-router-dom'
import { AppHeader } from './AppHeader'

export function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  const isHome = location.pathname === '/'
  const isNewMeeting = location.pathname === '/meetings/new'

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader zone="workspace" />
      <div className="border-b border-slate-800/60 bg-slate-950/60">
        <div className="page-container flex items-center gap-2 py-2.5 sm:gap-4 sm:py-3">
          <Link
            to="/"
            className={`btn-secondary min-h-9 shrink-0 px-3 py-2 text-xs sm:min-h-10 sm:px-4 sm:text-sm ${
              isHome ? 'border-indigo-500/40 bg-indigo-950/30 text-indigo-200' : ''
            }`}
          >
            Meetings
          </Link>
          <Link
            to="/meetings/new"
            className={`btn-primary min-h-9 shrink-0 px-3 py-2 text-xs sm:min-h-10 sm:px-4 sm:text-sm ${
              isNewMeeting ? 'ring-2 ring-indigo-400/50' : ''
            }`}
          >
            <span className="sm:hidden">+ New</span>
            <span className="hidden sm:inline">New meeting</span>
          </Link>
        </div>
      </div>
      <main className="page-container page-main min-w-0 flex-1">{children}</main>
    </div>
  )
}
