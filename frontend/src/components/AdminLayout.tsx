import { NavLink } from 'react-router-dom'
import { AdminSeedPanel } from './admin/AdminSeedPanel'
import { AppHeader } from './AppHeader'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm ${
    isActive
      ? 'bg-indigo-600/20 font-medium text-indigo-200'
      : 'text-slate-400 hover:bg-slate-800/60 hover:text-white'
  }`

export function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <AppHeader zone="admin" />
      <div className="mx-auto flex max-w-6xl gap-8 px-4 py-8">
        <aside className="w-48 shrink-0">
          <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Quản trị
          </p>
          <nav className="space-y-1">
            <NavLink to="/admin/personas" className={navLinkClass}>
              Personas
            </NavLink>
            <NavLink to="/admin/company" className={navLinkClass}>
              Company profile
            </NavLink>
            <NavLink to="/admin/meetings" className={navLinkClass}>
              All meetings
            </NavLink>
          </nav>
          <AdminSeedPanel />
        </aside>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  )
}
