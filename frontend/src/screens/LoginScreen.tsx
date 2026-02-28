import { IconAlertCircle, IconScissors } from '../components/Icons'

interface LoginScreenProps {
  error?: string | null
  onRetry?: () => void
}

export default function LoginScreen({ error, onRetry }: LoginScreenProps) {
  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--bk-red)]/10">
          <IconAlertCircle size={28} className="text-[var(--bk-red)]" />
        </div>
        <p className="bk-heading text-xl text-[var(--bk-text)]">Ошибка авторизации</p>
        <p className="text-sm text-[var(--bk-text-secondary)]">{error}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-2 rounded-xl bg-[var(--bk-gold)] px-8 py-2.5 text-sm font-semibold text-[var(--bk-bg-primary)]"
          >
            Попробовать снова
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--bk-gold)]/10 text-[var(--bk-gold)]">
        <IconScissors size={32} />
      </div>
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--bk-gold)] border-t-transparent" />
      <p className="text-sm text-[var(--bk-text-secondary)]">Авторизация...</p>
    </div>
  )
}
