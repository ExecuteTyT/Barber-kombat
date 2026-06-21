/** Shown in production when the app is opened outside Telegram (no initData). */
export default function OutsideTelegramScreen() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--bk-bg-elevated)] text-3xl">
        ✂️
      </div>
      <h1 className="bk-heading text-2xl text-[var(--bk-text)]">MAKON</h1>
      <p className="mt-2 max-w-xs text-sm text-[var(--bk-text-secondary)]">
        Приложение открывается внутри Telegram. Откройте бота и нажмите кнопку меню.
      </p>
      <a
        href="https://t.me/makon_app_bot"
        className="mt-5 rounded-xl bg-[var(--bk-gold)] px-5 py-2.5 text-sm font-semibold text-[var(--bk-bg-primary)]"
      >
        Открыть в Telegram
      </a>
    </div>
  )
}
