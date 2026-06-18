import { NavLink } from 'react-router-dom'
import { AdminSeedPanel } from './admin/AdminSeedPanel'
import { AppHeader } from './AppHeader'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `scroll-tabs-item ${
    isActive
      ? 'border-indigo-500 text-indigo-200'
      : 'border-transparent text-slate-400 hover:border-slate-600 hover:text-slate-200'
  }`

const sidebarLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block min-h-11 rounded-xl px-3 py-2.5 text-sm ${
    isActive
      ? 'bg-indigo-600/20 font-medium text-indigo-200'
      : 'text-slate-400 hover:bg-slate-800/60 hover:text-white'
  }`

const adminNavItems = [
  { to: '/admin/personas', label: 'Personas' },
  { to: '/admin/company', label: 'Company' },
  { to: '/admin/meetings', label: 'Meetings' },
] as const

export function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader zone="admin" />
      <nav className="scroll-tabs lg:hidden" aria-label="Admin navigation">
        {adminNavItems.map((item) => (
          <NavLink key={item.to} to={item.to} className={navLinkClass}>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="page-container flex flex-1 flex-col gap-6 py-4 sm:gap-8 sm:py-8 lg:flex-row">
        <aside className="hidden w-52 shrink-0 lg:block">
          <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Quản trị
          </p>
          <nav className="space-y-1">
            {adminNavItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={sidebarLinkClass}>
                {item.label === 'Company' ? 'Company profile' : item.label === 'Meetings' ? 'All meetings' : item.label}
              </NavLink>
            ))}
          </nav>
          <AdminSeedPanel />
        </aside>
        <main className="min-w-0 flex-1 pb-[max(1rem,env(safe-area-inset-bottom))]">{children}</main>
      </div>
      <div className="border-t border-slate-800 px-4 py-4 lg:hidden">
        <AdminSeedPanel compact />
      </div>
    </div>
  )
}
