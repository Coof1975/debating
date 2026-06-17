import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom'
import { AdminMeetingsPage } from './pages/admin/AdminMeetingsPage'
import { CompanyProfilePage } from './pages/CompanyProfilePage'
import { HomePage } from './pages/HomePage'
import { MeetingHubIndexRedirect, MeetingHubPage } from './pages/meeting/MeetingHubPage'
import { MeetingChatTab } from './pages/meeting/MeetingChatTab'
import { MeetingOverviewTab } from './pages/meeting/MeetingOverviewTab'
import { MeetingSimulationTab } from './pages/meeting/MeetingSimulationTab'
import { NewMeetingPage } from './pages/NewMeetingPage'
import { PersonaEditPage } from './pages/PersonaEditPage'
import { PersonasPage } from './pages/PersonasPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/meetings/new" element={<NewMeetingPage />} />
        <Route path="/meetings/:id" element={<MeetingHubPage />}>
          <Route index element={<MeetingHubIndexRedirect />} />
          <Route path="overview" element={<MeetingOverviewTab />} />
          <Route path="simulation" element={<MeetingSimulationTab />} />
          <Route path="chat" element={<MeetingChatTab />} />
        </Route>

        <Route path="/admin/personas" element={<PersonasPage />} />
        <Route path="/admin/personas/new" element={<PersonaEditPage />} />
        <Route path="/admin/personas/:role" element={<PersonaEditPage />} />
        <Route path="/admin/company" element={<CompanyProfilePage />} />
        <Route path="/admin/meetings" element={<AdminMeetingsPage />} />

        <Route path="/personas" element={<Navigate to="/admin/personas" replace />} />
        <Route path="/personas/new" element={<Navigate to="/admin/personas/new" replace />} />
        <Route path="/personas/:role" element={<PersonaEditRedirect />} />
        <Route path="/settings/company" element={<Navigate to="/admin/company" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

function PersonaEditRedirect() {
  const { role } = useParams<{ role: string }>()
  return <Navigate to={`/admin/personas/${role ?? ''}`} replace />
}
