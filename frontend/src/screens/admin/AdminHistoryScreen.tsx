import { useEffect, useState } from 'react'

import { IconArrowLeft, IconArrowRight } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAdminStore } from '../../stores/adminStore'
import { useAuthStore } from '../../stores/authStore'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function getMonthLabel(offset: number): string {
  const d = new Date()
  d.setMonth(d.getMonth() + offset)
  return d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
}

function getMonthParam(offset: number): string {
  const d = new Date()
  d.setMonth(d.getMonth() + offset)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

export default function AdminHistoryScreen() {
  const { user } = useAuthStore()
  const { history, loading, error, fetchHistory } = useAdminStore()
  const [monthOffset, setMonthOffset] = useState(0)

  useEffect(() => {
    if (user?.branch_id) {
      fetchHistory(user.branch_id, getMonthParam(monthOffset))
    }
  }, [user?.branch_id, monthOffset, fetchHistory])

  if (loading && !history) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">История</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">История</h1>
        <p className="mt-4 text-center text-sm text-[var(--bk-red)]">{error}</p>
      </div>
    )
  }

  const days = history?.days ?? []

  const totalRecords = days.reduce((s, d) => s + d.records_count, 0)
  const totalProducts = days.reduce((s, d) => s + d.products_sold, 0)
  const totalRevenue = days.reduce((s, d) => s + d.revenue, 0)
  const avgConfirmed =
    days.length > 0 ? Math.round(days.reduce((s, d) => s + d.confirmed_rate, 0) / days.length) : 0

  return (
    <div className="pb-4 pt-4">
      <h1 className="bk-heading px-4 text-xl">История</h1>

      {/* Month navigation */}
      <div className="mx-4 mt-3 flex items-center justify-between">
        <button
          type="button"
          className="rounded-lg p-2 text-[var(--bk-gold)] active:bg-[var(--bk-gold)]/10"
          onClick={() => setMonthOffset((o) => o - 1)}
        >
          <IconArrowLeft size={20} />
        </button>
        <span className="bk-heading text-sm capitalize">{getMonthLabel(monthOffset)}</span>
        <button
          type="button"
          className="rounded-lg p-2 text-[var(--bk-gold)] disabled:text-[var(--bk-text-dim)] disabled:opacity-30"
          onClick={() => setMonthOffset((o) => o + 1)}
          disabled={monthOffset >= 0}
        >
          <IconArrowRight size={20} />
        </button>
      </div>

      {/* Summary */}
      <div className="mx-4 mt-3 grid grid-cols-2 gap-2">
        {[
          { label: 'Записей', value: String(totalRecords) },
          { label: 'Товаров', value: String(totalProducts) },
          { label: 'Выручка', value: formatMoney(totalRevenue) },
          { label: 'Подтверждено', value: `${avgConfirmed}%` },
        ].map((s) => (
          <div key={s.label} className="bk-card p-3 text-center">
            <p className="text-xs text-[var(--bk-text-secondary)]">{s.label}</p>
            <p
              className="text-lg font-bold tabular-nums"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {s.value}
            </p>
          </div>
        ))}
      </div>

      {/* Day list */}
      <div className="mx-4 mt-4 space-y-1.5">
        {days.length === 0 && (
          <p className="py-6 text-center text-sm text-[var(--bk-text-secondary)]">
            Нет данных за этот месяц
          </p>
        )}
        {[...days].reverse().map((day) => {
          const date = new Date(day.date)
          const dayNum = date.getDate()
          const weekday = date.toLocaleDateString('ru-RU', { weekday: 'short' })

          return (
            <div key={day.date} className="bk-card flex items-center gap-3 px-3 py-3">
              <div className="w-10 text-center">
                <p
                  className="text-lg font-bold tabular-nums leading-tight"
                  style={{ fontFamily: 'var(--bk-font-heading)' }}
                >
                  {dayNum}
                </p>
                <p className="text-[10px] uppercase tracking-wider text-[var(--bk-text-dim)]">
                  {weekday}
                </p>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-[var(--bk-text)]">{day.records_count} записей</span>
                  <span className="text-sm font-bold tabular-nums text-[var(--bk-text)]">
                    {formatMoney(day.revenue)}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-[var(--bk-text-dim)]">
                  <span>{day.products_sold} тов.</span>
                  <span>{day.confirmed_rate}% подтв.</span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
