import { WorkspaceLayout } from '../components/WorkspaceLayout'
import { MeetingWizard } from '../components/meeting/MeetingWizard'

export function NewMeetingPage() {
  return (
    <WorkspaceLayout>
      <h1 className="text-2xl font-semibold text-white">Tạo meeting mới</h1>
      <p className="mt-1 text-slate-400">
        Thiết lập cuộc họp trước, sau đó chạy simulation khi sẵn sàng.
      </p>
      <div className="mt-8">
        <MeetingWizard />
      </div>
    </WorkspaceLayout>
  )
}
