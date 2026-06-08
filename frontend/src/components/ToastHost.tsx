import { IconAlertCircle, IconCheckCircle } from './Icons'
import { useToastStore } from '../stores/toastStore'

/** Global toast outlet — mount once near the app root. Sits above modals. */
export default function ToastHost() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  if (toasts.length === 0) return null

  return (
    <div
      className="pointer-events-none fixed inset-x-0 top-0 z-[70] flex flex-col items-center gap-2 p-3"
      style={{ paddingTop: 'calc(env(safe-area-inset-top) + 0.5rem)' }}
    >
      {toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => dismiss(t.id)}
          className={`bk-fade-in pointer-events-auto flex max-w-sm items-center gap-2 rounded-xl px-4 py-3 text-sm font-medium shadow-lg ${
            t.type === 'success'
              ? 'bg-[var(--bk-green)] text-white'
              : t.type === 'error'
                ? 'bg-[var(--bk-red)] text-white'
                : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text)]'
          }`}
        >
          {t.type === 'success' && <IconCheckCircle size={16} />}
          {t.type === 'error' && <IconAlertCircle size={16} />}
          <span>{t.message}</span>
        </button>
      ))}
    </div>
  )
}
