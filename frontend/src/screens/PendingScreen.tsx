import { IconScissors } from '../components/Icons'
import type { PendingInfo } from '../types'

/** Shown when a Telegram user opened the app but isn't linked to a user yet. */
export default function PendingScreen({ info }: { info: PendingInfo }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-8 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--bk-bg-elevated)]">
        <IconScissors size={32} className="text-[var(--bk-gold)]" />
      </div>
      <h1 className="bk-heading mt-4 text-2xl">MAKON</h1>
      <p className="mt-3 text-sm text-[var(--bk-text)]">Доступ ещё не открыт</p>
      <p className="mt-2 max-w-xs text-sm text-[var(--bk-text-secondary)]">
        Передайте эти данные владельцу — он добавит вас, и доступ появится.
      </p>
      <div className="mt-4 w-full max-w-xs rounded-xl bg-[var(--bk-bg-elevated)] p-3 text-left">
        {info.name && (
          <p className="text-sm text-[var(--bk-text)]">{info.name}</p>
        )}
        {info.username && (
          <p className="text-sm text-[var(--bk-text-secondary)]">@{info.username}</p>
        )}
        <p className="text-xs text-[var(--bk-text-dim)]">Telegram ID: {info.telegram_id}</p>
      </div>
    </div>
  )
}
