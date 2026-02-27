interface LoginScreenProps {
  error?: string | null
  onRetry?: () => void
}

export default function LoginScreen({ error, onRetry }: LoginScreenProps) {
  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
        <p className="text-lg font-medium text-[var(--tg-theme-text-color)]">
          Ошибка авторизации
        </p>
        <p className="text-sm text-[var(--tg-theme-hint-color)]">{error}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="rounded-lg bg-[var(--tg-theme-button-color)] px-6 py-2 text-[var(--tg-theme-button-text-color)]"
          >
            Попробовать снова
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--tg-theme-button-color)] border-t-transparent" />
      <p className="text-sm text-[var(--tg-theme-hint-color)]">Авторизация...</p>
    </div>
  )
}
