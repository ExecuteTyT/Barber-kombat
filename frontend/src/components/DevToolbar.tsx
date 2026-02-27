import { useAuthStore } from '../stores/authStore'

/**
 * Floating dev toolbar shown only in dev mode (outside Telegram).
 * Allows quick role switching and logout.
 */
export default function DevToolbar() {
  const { user, logout } = useAuthStore()

  if (!user) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between border-t border-gray-700 bg-gray-900/95 px-3 py-1.5 text-xs text-gray-400 backdrop-blur-sm">
      <span>
        DEV: <span className="font-medium text-white">{user.name}</span>{' '}
        <span className="rounded bg-gray-700 px-1.5 py-0.5 text-gray-300">{user.role}</span>
      </span>
      <button
        onClick={logout}
        className="rounded bg-gray-700 px-2 py-0.5 text-gray-300 transition-colors hover:bg-gray-600"
      >
        Сменить
      </button>
    </div>
  )
}
