import { useEffect } from 'react'

import { MedalBadge, IconShoppingBag, IconGift, IconStar, IconUsers } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAuthStore } from '../../stores/authStore'
import { useChefAnalyticsStore } from '../../stores/chefAnalyticsStore'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function KPICard({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub?: string
  accent?: boolean
}) {
  return (
    <div className="bk-card p-3">
      <p className="text-xs text-[var(--bk-text-secondary)]">{label}</p>
      <p
        className={`mt-1 text-lg font-bold tabular-nums ${accent ? 'text-[var(--bk-gold)]' : 'text-[var(--bk-text)]'}`}
        style={{ fontFamily: 'var(--bk-font-heading)' }}
      >
        {value}
      </p>
      {sub && <p className="mt-0.5 text-xs tabular-nums text-[var(--bk-text-dim)]">{sub}</p>}
    </div>
  )
}

function StatCell({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon?: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-2 rounded-xl bg-[var(--bk-bg-elevated)] p-3">
      {icon && <span className="text-[var(--bk-text-secondary)]">{icon}</span>}
      <div className="min-w-0">
        <p className="text-xs text-[var(--bk-text-secondary)]">{label}</p>
        <p className="text-sm font-semibold tabular-nums text-[var(--bk-text)]">{value}</p>
      </div>
    </div>
  )
}

export default function ChefAnalyticsScreen() {
  const user = useAuthStore((s) => s.user)
  const branchId = user?.branch_id
  const { analytics, loading, error, fetchAnalytics } = useChefAnalyticsStore()

  useEffect(() => {
    if (branchId) {
      fetchAnalytics(branchId)
    }
  }, [branchId, fetchAnalytics])

  if (!branchId) {
    return <div className="p-8 text-center text-[var(--bk-text-secondary)]">Филиал не назначен</div>
  }

  if (loading && !analytics) {
    return (
      <div className="px-4 pt-4">
        <h1 className="bk-heading text-xl">Аналитика</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error && !analytics) {
    return (
      <div className="px-4 pt-4">
        <h1 className="bk-heading text-xl">Аналитика</h1>
        <div className="mt-4 rounded-xl bg-[var(--bk-bg-card)] p-4 text-center text-sm text-[var(--bk-red)]">
          {error}
        </div>
      </div>
    )
  }

  if (!analytics) return null

  return (
    <div className="pb-4 pt-4">
      {/* Header */}
      <div className="px-4">
        <h1 className="bk-heading text-xl">Аналитика</h1>
        <p className="mt-0.5 text-xs text-[var(--bk-text-secondary)]">{analytics.branch_name}</p>
      </div>

      {/* KPI cards 2x2 */}
      <div className="bk-fade-up mx-4 mt-3 grid grid-cols-2 gap-2">
        <KPICard
          label="Выручка сегодня"
          value={formatMoney(analytics.revenue_today)}
          sub={`МТД: ${formatMoney(analytics.revenue_mtd)}`}
        />
        <KPICard
          label="Средний чек"
          value={formatMoney(analytics.avg_check_today)}
          sub={`МТД: ${formatMoney(analytics.avg_check_mtd)}`}
        />
        <KPICard
          label="Клиентов сегодня"
          value={String(analytics.clients_today)}
          sub={`Визитов: ${analytics.visits_today}`}
        />
        <KPICard
          label="Выполнение плана"
          value={`${analytics.plan_percentage.toFixed(0)}%`}
          accent
        />
      </div>

      {/* Revenue progress bar */}
      <div className="bk-fade-up mx-4 mt-3" style={{ animationDelay: '0.05s' }}>
        <div className="bk-card p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-[var(--bk-text-secondary)]">План месяца</span>
            <span className="text-sm font-bold tabular-nums text-[var(--bk-gold)]">
              {analytics.plan_percentage.toFixed(0)}%
            </span>
          </div>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
            <div
              className="bk-progress-fill h-full transition-all duration-700"
              style={{ width: `${Math.min(analytics.plan_percentage, 100)}%` }}
            />
          </div>
          <div className="mt-1.5 flex justify-between text-xs tabular-nums text-[var(--bk-text-dim)]">
            <span>{formatMoney(analytics.revenue_mtd)}</span>
            <span>{formatMoney(analytics.plan_target)}</span>
          </div>
        </div>
      </div>

      {/* Top barbers */}
      {analytics.top_barbers.length > 0 && (
        <div className="bk-fade-up mx-4 mt-4" style={{ animationDelay: '0.1s' }}>
          <h3 className="bk-heading text-base">Топ барберов</h3>
          <div className="mt-2 space-y-2">
            {analytics.top_barbers.map((b, i) => (
              <div key={b.barber_id} className="bk-card flex items-center gap-3 p-3">
                <MedalBadge rank={i + 1} size={28} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[var(--bk-text)]">{b.name}</p>
                  <p className="text-xs text-[var(--bk-text-secondary)]">
                    {b.days_worked} дн. / {b.wins} побед / {b.avg_score.toFixed(1)} балл
                  </p>
                </div>
                <span
                  className="text-sm font-bold tabular-nums text-[var(--bk-text)]"
                  style={{ fontFamily: 'var(--bk-font-heading)' }}
                >
                  {formatMoney(b.revenue)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Month stats grid */}
      <div className="bk-fade-up mx-4 mt-4" style={{ animationDelay: '0.15s' }}>
        <h3 className="bk-heading text-base">Статистика месяца</h3>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <StatCell
            label="Товаров продано"
            value={String(analytics.total_products_mtd)}
            icon={<IconShoppingBag size={16} />}
          />
          <StatCell
            label="Допуслуг"
            value={String(analytics.total_extras_mtd)}
            icon={<IconGift size={16} />}
          />
          <StatCell
            label="Средний отзыв"
            value={
              analytics.avg_review_score !== null ? analytics.avg_review_score.toFixed(1) : '—'
            }
            icon={<IconStar size={16} />}
          />
          <StatCell
            label="В смене"
            value={`${analytics.barbers_in_shift}/${analytics.barbers_total}`}
            icon={<IconUsers size={16} />}
          />
          <StatCell label="Визитов МТД" value={String(analytics.visits_mtd)} />
          <StatCell label="Новых клиентов" value={String(analytics.new_clients_mtd)} />
        </div>
      </div>
    </div>
  )
}
