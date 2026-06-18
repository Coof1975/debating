import { Link } from 'react-router-dom'

type AppHeaderProps = {
  zone: 'workspace' | 'admin'
}

export function AppHeader({ zone }: AppHeaderProps) {
  const homeTo = zone === 'admin' ? '/admin/personas' : '/'

  return (
    <header className="sticky top-0 z-40 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md supports-[backdrop-filter]:bg-slate-900/75">
      <div className="page-container flex min-h-14 items-center justify-between gap-3 py-2 sm:min-h-16 sm:py-3">
        <Link
          to={homeTo}
          className="min-w-0 truncate text-base font-semibold tracking-tight text-white sm:text-lg"
        >
          <span className="sm:hidden">Debating</span>
          <span className="hidden sm:inline">Debating Simulator</span>
        </Link>
        <div className="flex shrink-0 items-center">
          <div className="flex rounded-xl border border-slate-700 p-0.5 text-xs font-medium">
            <Link
              to="/"
              className={`rounded-lg px-2.5 py-2 sm:px-3 sm:py-1.5 ${
                zone === 'workspace'
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Workspace
            </Link>
            <Link
              to="/admin/personas"
              className={`rounded-lg px-2.5 py-2 sm:px-3 sm:py-1.5 ${
                zone === 'admin'
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Admin
            </Link>
          </div>
        </div>
      </div>
    </header>
  )
}
