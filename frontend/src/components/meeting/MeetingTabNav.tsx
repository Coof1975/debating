import { NavLink } from 'react-router-dom'
import {
  canAccessChatTab,
  canAccessSimulationTab,
} from '../../pages/meeting/MeetingHubContext'

type MeetingTabNavProps = {
  meetingId: string
  status: string
}

const activeClass = 'border-indigo-500 text-indigo-200'
const inactiveClass =
  'border-transparent text-slate-400 hover:border-slate-600 hover:text-slate-200'
const disabledClass = 'border-transparent text-slate-600 cursor-not-allowed'

export function MeetingTabNav({ meetingId, status }: MeetingTabNavProps) {
  const base = `/meetings/${meetingId}`
  const simEnabled = canAccessSimulationTab(status)
  const chatEnabled = canAccessChatTab(status)

  const tabClass = (isActive: boolean) =>
    `scroll-tabs-item -mb-px ${isActive ? activeClass : inactiveClass}`

  return (
    <nav
      className="scroll-tabs mb-6 sm:mb-8"
      aria-label="Meeting sections"
    >
      <NavLink to={`${base}/overview`} className={({ isActive }) => tabClass(isActive)}>
        Tổng quan
      </NavLink>

      {simEnabled ? (
        <NavLink to={`${base}/simulation`} className={({ isActive }) => tabClass(isActive)}>
          Simulation
        </NavLink>
      ) : (
        <span className={`scroll-tabs-item -mb-px ${disabledClass}`}>Simulation</span>
      )}

      {chatEnabled ? (
        <NavLink to={`${base}/chat`} className={({ isActive }) => tabClass(isActive)}>
          Chat
        </NavLink>
      ) : (
        <span
          className={`scroll-tabs-item -mb-px ${disabledClass}`}
          title="Hoàn thành simulation trước khi chat"
        >
          Chat
        </span>
      )}
    </nav>
  )
}
