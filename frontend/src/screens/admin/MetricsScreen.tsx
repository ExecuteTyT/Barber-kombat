import { useEffect } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAdminStore } from '../../stores/adminStore'
import { useAuthStore } from '../../stores/authStore'

export default function MetricsScreen() {
  const { user } = useAuthStore()
  const { metrics, loading, error, fetchMetrics } = useAdminStore()

  useEffect(() => {
    if (user?.branch_id) {
      fetchMetrics(user.branch_id)
    }
  }, [user?.branch_id, fetchMetrics])

  if (loading && !metrics) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="text-lg font-bold">Показатели</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="text-lg font-bold">Показатели</h1>
        <p className="mt-4 text-center text-sm text-red-500">{error}</p>
      </div>
    )
  }

  if (!metrics) return null

  const cards = [
    {
      label: 'Записей сегодня',
      value: String(metrics.records_today),
      hint: 'внесено вручную',
      icon: '\u{1F4CB}',
    },
    {
      label: 'Продано товаров',
      value: `${metrics.products_sold} шт`,
      hint: null,
      icon: '\u{1F6CD}\u{FE0F}',
    },
    {
      label: 'Подтверждено на завтра',
      value: `${metrics.confirmed_tomorrow} / ${metrics.total_tomorrow}`,
      hint: 'записей',
      icon: '\u{2705}',
    },
    {
      label: 'Заполненных ДР',
      value: `${metrics.filled_birthdays} / ${metrics.total_clients}`,
      hint: 'клиентов',
      icon: '\u{1F382}',
    },
  ]

  return (
    <div className="pb-4 pt-4">
      <h1 className="px-4 text-lg font-bold">Показатели</h1>
      <p className="mt-1 px-4 text-xs text-[var(--tg-theme-hint-color)]">
        {metrics.branch_name} {'\u{2022}'} {metrics.date}
      </p>

      <div className="mx-4 mt-4 space-y-3">
        {cards.map((card) => (
          <div
            key={card.label}
            className="flex items-center gap-3 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4"
          >
            <span className="text-2xl">{card.icon}</span>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-[var(--tg-theme-hint-color)]">{card.label}</p>
              <p className="text-xl font-bold tabular-nums">{card.value}</p>
              {card.hint && (
                <p className="text-xs text-[var(--tg-theme-hint-color)]">{card.hint}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
