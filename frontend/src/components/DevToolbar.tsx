import { useAuthStore } from '../stores/authStore'

export default function DevToolbar() {
  const { user, logout } = useAuthStore()

  if (!user) return null

  return (
    <div className="fixed top-0 left-0 right-0 z-[60] flex items-center justify-between border-b border-[var(--bk-border-gold)] bg-[var(--bk-bg-primary)]/95 px-3 py-1.5 text-xs backdrop-blur-sm">
      <span className="text-[var(--bk-text-secondary)]">
        DEV: <span className="font-medium text-[var(--bk-gold)]">{user.name}</span>{' '}
        <span className="rounded bg-[var(--bk-bg-elevated)] px-1.5 py-0.5 text-[var(--bk-text-secondary)]">
          {user.role}
        </span>
      </span>
      <button
        onClick={logout}
        className="rounded bg-[var(--bk-bg-elevated)] px-2 py-0.5 text-[var(--bk-text-secondary)] transition-colors hover:text-[var(--bk-gold)]"
      >
        Сменить
      </button>
    </div>
  )
}
