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
      className={`btn-primary w-full sm:w-auto ${className}`}
    >
      {loading ? 'Đang khởi chạy…' : label}
    </button>
  )
}
