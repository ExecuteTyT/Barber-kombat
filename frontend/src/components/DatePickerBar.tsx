import { IconArrowLeft, IconArrowRight } from './Icons'

/** Format a Date as YYYY-MM-DD using its LOCAL calendar fields. */
function fmtLocal(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** ISO date (YYYY-MM-DD) for today in local time. */
export function todayIso(): string {
  return fmtLocal(new Date())
}

/**
 * Shift an ISO date by whole days, staying entirely in local time.
 * (Using toISOString() here would convert to UTC and drop/keep a day in
 * non-UTC zones — e.g. UTC+3 made "next day" resolve back to the same date.)
 */
function shiftIso(iso: string, deltaDays: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  dt.setDate(dt.getDate() + deltaDays)
  return fmtLocal(dt)
}

/** Prev / date / next picker with a "Сегодня" shortcut. Cannot go past today. */
export default function DatePickerBar({
  value,
  onChange,
}: {
  value: string
  onChange: (iso: string) => void
}) {
  const today = todayIso()
  const isToday = value === today
  const canGoForward = value < today

  const go = (delta: number) => (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onChange(shiftIso(value, delta))
  }

  return (
    <div className="mb-3 flex items-center gap-2">
      <button
        type="button"
        className="rounded-lg bg-[var(--bk-bg-elevated)] p-2 text-[var(--bk-gold)] active:opacity-70"
        onClick={go(-1)}
        aria-label="Предыдущий день"
      >
        <IconArrowLeft size={16} className="pointer-events-none" />
      </button>
      <input
        type="date"
        className="flex-1 rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-2 py-1.5 text-sm text-[var(--bk-text)]"
        value={value}
        max={today}
        onChange={(e) => e.target.value && onChange(e.target.value)}
      />
      <button
        type="button"
        className="rounded-lg bg-[var(--bk-bg-elevated)] p-2 text-[var(--bk-gold)] disabled:opacity-30"
        disabled={!canGoForward}
        onClick={go(1)}
        aria-label="Следующий день"
      >
        <IconArrowRight size={16} className="pointer-events-none" />
      </button>
      {!isToday && (
        <button
          type="button"
          className="rounded-lg bg-[var(--bk-gold)] px-2.5 py-1.5 text-xs font-semibold text-[var(--bk-bg-primary)]"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onChange(today)
          }}
        >
          Сегодня
        </button>
      )}
    </div>
  )
}
