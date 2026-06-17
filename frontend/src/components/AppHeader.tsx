import { Link } from 'react-router-dom'

type AppHeaderProps = {
  zone: 'workspace' | 'admin'
}

export function AppHeader({ zone }: AppHeaderProps) {
  const homeTo = zone === 'admin' ? '/admin/personas' : '/'

  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link to={homeTo} className="text-lg font-semibold tracking-tight text-white">
          Debating Simulator
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex rounded-lg border border-slate-700 p-0.5 text-xs font-medium">
            <Link
              to="/"
              className={`rounded-md px-3 py-1.5 ${
                zone === 'workspace'
                  ? 'bg-indigo-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Workspace
            </Link>
            <Link
              to="/admin/personas"
              className={`rounded-md px-3 py-1.5 ${
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
