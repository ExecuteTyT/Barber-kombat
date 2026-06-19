import { useEffect } from 'react'

import { IconClipboard, IconShoppingBag, IconCheckCircle } from '../../components/Icons'
import InfoTip from '../../components/InfoTip'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAdminStore } from '../../stores/adminStore'
import { useAuthStore } from '../../stores/authStore'

function KpiChip({ label, value, tip }: { label: string; value: string; tip?: string }) {
  return (
    <div className="rounded-lg bg-[var(--bk-bg-primary)] px-2.5 py-1.5">
      <p className="flex items-center text-[var(--bk-text-dim)]">
        {label}
        {tip && <InfoTip text={tip} />}
      </p>
      <p className="font-semibold tabular-nums text-[var(--bk-text)]">{value}</p>
    </div>
  )
}

export default function MetricsScreen() {
  const { user } = useAuthStore()
  const { metrics, branchKpi, loading, error, fetchMetrics, fetchBranchKpi } = useAdminStore()

  useEffect(() => {
    if (user?.branch_id) {
      fetchMetrics(user.branch_id)
      fetchBranchKpi(user.branch_id)
    }
  }, [user?.branch_id, fetchMetrics, fetchBranchKpi])

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
  ]

  return (
    <div className="pb-4 pt-4">
      <h1 className="bk-heading px-4 text-xl">Показатели</h1>
      <p className="mt-1 px-4 text-xs text-[var(--bk-text-secondary)]">
        {metrics.branch_name} {'•'} {metrics.date}
      </p>

      {/* Admin KPI hero (survey + confirmation composite) */}
      {branchKpi && (
        <div className="mx-4 mt-4 rounded-2xl border border-[var(--bk-border-gold)] bg-[var(--bk-bg-elevated)] p-4">
          <div className="flex items-end justify-between">
            <div>
              <p className="flex items-center text-xs text-[var(--bk-text-secondary)]">
                KPI администратора
                <InfoTip text="Итоговый балл админа: 60% — средняя оценка гостей из опроса, 40% — доля подтверждённых записей. Чем выше, тем лучше работает админ." />
              </p>
              <p
                className="text-4xl font-bold tabular-nums text-[var(--bk-gold)]"
                style={{ fontFamily: 'var(--bk-font-heading)' }}
              >
                {branchKpi.composite_score ?? '—'}
                <span className="text-lg text-[var(--bk-text-dim)]">/100</span>
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--bk-text-dim)]">
                60% опросы + 40% подтверждения
              </p>
            </div>
            <p className="text-xs text-[var(--bk-text-dim)]">
              {branchKpi.survey_count} опросов за месяц
            </p>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <KpiChip
              label="Оценка админа"
              value={branchKpi.admin_avg != null ? `${branchKpi.admin_avg}` : '—'}
              tip="Средний балл работы админа из гостевых опросов (0–100): приветствие, зона ожидания, напитки, рассказ про акции, предложение перезаписи и вежливость общения."
            />
            <KpiChip
              label="Подтверждения"
              value={branchKpi.confirmation_rate != null ? `${branchKpi.confirmation_rate}%` : '—'}
              tip="Доля ближайших записей, подтверждённых клиентами (флаг подтверждения из YClients). Показывает, что записи обзвонены/подтверждены."
            />
            <KpiChip
              label="Рекомендуют"
              value={branchKpi.nps != null ? `${branchKpi.nps}%` : '—'}
              tip="Доля гостей, готовых порекомендовать барбершоп — из ответа «Порекомендуете?» в опросе. В маркетинге это называют NPS (индекс лояльности)."
            />
            <KpiChip
              label="Средн. звёзды"
              value={branchKpi.stars_avg != null ? `${branchKpi.stars_avg}` : '—'}
              tip="Средняя оценка визита в звёздах (1–5) по гостевым опросам за месяц."
            />
          </div>
          {branchKpi.negatives > 0 && (
            <p className="mt-2 flex items-center text-xs text-[var(--bk-red)]">
              Негативных отзывов за месяц: {branchKpi.negatives}
              <InfoTip text="Сколько гостевых опросов за месяц отмечены негативными: низкие звёзды, «не порекомендую» или резкое общение. Их стоит разобрать." />
            </p>
          )}
        </div>
      )}

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
