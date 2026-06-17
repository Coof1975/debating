type RunSimulationButtonProps = {
  onClick: () => void
  loading?: boolean
  label?: string
  className?: string
}

export function RunSimulationButton({
  onClick,
  loading = false,
  label = 'Chạy simulation',
  className = '',
}: RunSimulationButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className={`rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50 ${className}`}
    >
      {loading ? 'Đang khởi chạy…' : label}
    </button>
  )
}
