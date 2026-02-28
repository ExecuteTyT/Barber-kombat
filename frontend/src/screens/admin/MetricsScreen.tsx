import { useEffect } from 'react'

import { IconClipboard, IconShoppingBag, IconCheckCircle, IconGift } from '../../components/Icons'
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
        <h1 className="bk-heading text-xl">Показатели</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">Показатели</h1>
        <p className="mt-4 text-center text-sm text-[var(--bk-red)]">{error}</p>
      </div>
    )
  }

  if (!metrics) return null

  const cards = [
    {
      label: 'Записей сегодня',
      value: String(metrics.records_today),
      hint: 'внесено вручную',
      icon: <IconClipboard size={24} className="text-[var(--bk-gold)]" />,
      color: 'var(--bk-gold)',
    },
    {
      label: 'Продано товаров',
      value: `${metrics.products_sold} шт`,
      hint: null,
      icon: <IconShoppingBag size={24} className="text-[var(--bk-score-cs)]" />,
      color: 'var(--bk-score-cs)',
    },
    {
      label: 'Подтверждено на завтра',
      value: `${metrics.confirmed_tomorrow} / ${metrics.total_tomorrow}`,
      hint: 'записей',
      icon: <IconCheckCircle size={24} className="text-[var(--bk-green)]" />,
      color: 'var(--bk-green)',
    },
    {
      label: 'Заполненных ДР',
      value: `${metrics.filled_birthdays} / ${metrics.total_clients}`,
      hint: 'клиентов',
      icon: <IconGift size={24} className="text-[var(--bk-score-extras)]" />,
      color: 'var(--bk-score-extras)',
    },
  ]

  return (
    <div className="pb-4 pt-4">
      <h1 className="bk-heading px-4 text-xl">Показатели</h1>
      <p className="mt-1 px-4 text-xs text-[var(--bk-text-secondary)]">
        {metrics.branch_name} \u{2022} {metrics.date}
      </p>

      <div className="mx-4 mt-4 space-y-3">
        {cards.map((card, i) => (
          <div
            key={card.label}
            className="bk-card bk-fade-up flex items-center gap-4 p-4"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <div
              className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl"
              style={{ backgroundColor: `color-mix(in srgb, ${card.color} 15%, transparent)` }}
            >
              {card.icon}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm text-[var(--bk-text-secondary)]">{card.label}</p>
              <p
                className="text-xl font-bold tabular-nums"
                style={{ fontFamily: 'var(--bk-font-heading)' }}
              >
                {card.value}
              </p>
              {card.hint && <p className="text-xs text-[var(--bk-text-dim)]">{card.hint}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
