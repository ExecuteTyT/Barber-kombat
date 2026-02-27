import { useEffect, useState } from 'react'

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
        <h1 className="text-lg font-bold">История</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="text-lg font-bold">История</h1>
        <p className="mt-4 text-center text-sm text-red-500">{error}</p>
      </div>
    )
  }

  const days = history?.days ?? []

  // Summary stats
  const totalRecords = days.reduce((s, d) => s + d.records_count, 0)
  const totalProducts = days.reduce((s, d) => s + d.products_sold, 0)
  const totalRevenue = days.reduce((s, d) => s + d.revenue, 0)
  const avgConfirmed = days.length > 0
    ? Math.round(days.reduce((s, d) => s + d.confirmed_rate, 0) / days.length)
    : 0

  return (
    <div className="pb-4 pt-4">
      <h1 className="px-4 text-lg font-bold">История</h1>

      {/* Month navigation */}
      <div className="mx-4 mt-3 flex items-center justify-between">
        <button
          type="button"
          className="px-2 py-1 text-[var(--tg-theme-button-color)]"
          onClick={() => setMonthOffset((o) => o - 1)}
        >
          {'\u{2190}'}
        </button>
        <span className="text-sm font-medium capitalize">{getMonthLabel(monthOffset)}</span>
        <button
          type="button"
          className="px-2 py-1 text-[var(--tg-theme-button-color)] disabled:opacity-30"
          onClick={() => setMonthOffset((o) => o + 1)}
          disabled={monthOffset >= 0}
        >
          {'\u{2192}'}
        </button>
      </div>

      {/* Summary */}
      <div className="mx-4 mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-3 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">Записей</p>
          <p className="text-lg font-bold tabular-nums">{totalRecords}</p>
        </div>
        <div className="rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-3 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">Товаров</p>
          <p className="text-lg font-bold tabular-nums">{totalProducts}</p>
        </div>
        <div className="rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-3 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">Выручка</p>
          <p className="text-lg font-bold tabular-nums">{formatMoney(totalRevenue)}</p>
        </div>
        <div className="rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-3 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">Подтверждено</p>
          <p className="text-lg font-bold tabular-nums">{avgConfirmed}%</p>
        </div>
      </div>

      {/* Day list */}
      <div className="mx-4 mt-4 space-y-1">
        {days.length === 0 && (
          <p className="py-6 text-center text-sm text-[var(--tg-theme-hint-color)]">
            Нет данных за этот месяц
          </p>
        )}
        {[...days].reverse().map((day) => {
          const date = new Date(day.date)
          const dayNum = date.getDate()
          const weekday = date.toLocaleDateString('ru-RU', { weekday: 'short' })

          return (
            <div
              key={day.date}
              className="flex items-center gap-3 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] px-3 py-2.5"
            >
              <div className="w-10 text-center">
                <p className="text-lg font-bold tabular-nums leading-tight">{dayNum}</p>
                <p className="text-[10px] uppercase text-[var(--tg-theme-hint-color)]">{weekday}</p>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between">
                  <span className="text-sm">{day.records_count} записей</span>
                  <span className="text-sm font-bold tabular-nums">{formatMoney(day.revenue)}</span>
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-[var(--tg-theme-hint-color)]">
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
