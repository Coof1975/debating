import { NavLink } from 'react-router-dom'
import {
  canAccessChatTab,
  canAccessSimulationTab,
} from '../../pages/meeting/MeetingHubContext'

type MeetingTabNavProps = {
  meetingId: string
  status: string
}

const activeClass =
  'border-indigo-500 text-indigo-200'
const inactiveClass =
  'border-transparent text-slate-400 hover:border-slate-600 hover:text-slate-200'
const disabledClass =
  'border-transparent text-slate-600 cursor-not-allowed'

export function MeetingTabNav({ meetingId, status }: MeetingTabNavProps) {
  const base = `/meetings/${meetingId}`
  const simEnabled = canAccessSimulationTab(status)
  const chatEnabled = canAccessChatTab(status)

  return (
    <nav className="mb-8 flex gap-1 border-b border-slate-800">
      <NavLink
        to={`${base}/overview`}
        className={({ isActive }) =>
          `-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${isActive ? activeClass : inactiveClass}`
        }
      >
        Tổng quan
      </NavLink>

      {simEnabled ? (
        <NavLink
          to={`${base}/simulation`}
          className={({ isActive }) =>
            `-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${isActive ? activeClass : inactiveClass}`
          }
        >
          Simulation
        </NavLink>
      ) : (
        <span className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${disabledClass}`}>
          Simulation
        </span>
      )}

      {chatEnabled ? (
        <NavLink
          to={`${base}/chat`}
          className={({ isActive }) =>
            `-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${isActive ? activeClass : inactiveClass}`
          }
        >
          Chat
        </NavLink>
      ) : (
        <span
          className={`-mb-px border-b-2 px-4 py-2.5 text-sm font-medium ${disabledClass}`}
          title="Hoàn thành simulation trước khi chat"
        >
          Chat
        </span>
      )}
    </nav>
  )
}
