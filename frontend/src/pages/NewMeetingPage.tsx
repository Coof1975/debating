import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { MeetingWizard } from '../components/meeting/MeetingWizard'

export function NewMeetingPage() {
  return (
    <WorkspaceLayout>
      <div className="mb-6 sm:mb-8">
        <h1 className="page-title">Tạo meeting mới</h1>
        <p className="page-subtitle">
          Thiết lập cuộc họp trước, sau đó chạy simulation khi sẵn sàng.
        </p>
      </div>
      <MeetingWizard />
    </WorkspaceLayout>
  )
}
