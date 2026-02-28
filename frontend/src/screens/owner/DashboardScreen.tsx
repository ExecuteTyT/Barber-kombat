import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

import { IconUsers, IconChevronRight } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useOwnerStore } from '../../stores/ownerStore'
import type { BranchRevenue } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function BranchCard({ branch, onClick }: { branch: BranchRevenue; onClick: () => void }) {
  return (
    <button
      type="button"
      className="bk-card w-full p-4 text-left transition-all active:scale-[0.98]"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--bk-text)]">{branch.name}</span>
        <span className="flex items-center gap-1 text-sm text-[var(--bk-text-secondary)]">
          {branch.barbers_in_shift}/{branch.barbers_total}
          <IconUsers size={14} />
        </span>
      </div>

      <p
        className="mt-1.5 font-bold tabular-nums text-lg"
        style={{ fontFamily: 'var(--bk-font-heading)' }}
      >
        {formatMoney(branch.revenue_today)}{' '}
        <span
          className="text-sm font-normal text-[var(--bk-text-secondary)]"
          style={{ fontFamily: 'var(--bk-font-body)' }}
        >
          сегодня
        </span>
      </p>

      <div className="mt-3">
        <div className="h-2 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
          <div
            className="bk-progress-fill h-full transition-all duration-700"
            style={{ width: `${Math.min(branch.plan_percentage, 100)}%` }}
          />
        </div>
        <div className="mt-1.5 flex items-baseline justify-between text-xs">
          <span className="text-[var(--bk-text-dim)]">
            {formatMoney(branch.revenue_mtd)} / {formatMoney(branch.plan_target)}
          </span>
          <span className="font-bold tabular-nums text-[var(--bk-gold)]">
            {branch.plan_percentage.toFixed(0)}%
          </span>
        </div>
      </div>

      <div className="mt-2 flex justify-end">
        <IconChevronRight size={16} className="text-[var(--bk-text-dim)]" />
      </div>
    </button>
  )
}

export default function DashboardScreen() {
  const navigate = useNavigate()
  const { revenue, alarumTotal, isLoading, error, fetchDashboard, fetchAlarum } = useOwnerStore()

  useEffect(() => {
    fetchDashboard()
    fetchAlarum()
  }, [fetchDashboard, fetchAlarum])

  if (isLoading && !revenue) {
    return (
      <div className="p-4">
        <LoadingSkeleton lines={2} />
        <div className="mt-4 space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <LoadingSkeleton key={i} lines={4} />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-[var(--bk-red)]">{error}</p>
      </div>
    )
  }

  if (!revenue) return null

  return (
    <div className="pb-4 pt-4">
      <div className="px-4">
        <h1 className="bk-heading text-xl">Дашборд</h1>
        <div className="mt-3 flex gap-4">
          <div className="flex-1">
            <p className="text-xs text-[var(--bk-text-secondary)]">Сегодня</p>
            <p
              className="text-2xl font-bold tabular-nums"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {formatMoney(revenue.network_total_today)}
            </p>
          </div>
          <div className="flex-1">
            <p className="text-xs text-[var(--bk-text-secondary)]">С начала месяца</p>
            <p
              className="text-2xl font-bold tabular-nums"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {formatMoney(revenue.network_total_mtd)}
            </p>
          </div>
        </div>
        {alarumTotal > 0 && (
          <div className="mt-3 flex items-center gap-2 text-sm text-[var(--bk-red)]">
            <span className="bk-live-pulse inline-block h-2.5 w-2.5 rounded-full bg-[var(--bk-red)]" />
            {alarumTotal} необработанн{alarumTotal === 1 ? 'ый' : 'ых'} отзыв
            {alarumTotal === 1 ? '' : alarumTotal < 5 ? 'а' : 'ов'}
          </div>
        )}
      </div>

      <div className="mx-4 mt-5 space-y-3">
        {revenue.branches.map((branch, i) => (
          <div
            key={branch.branch_id}
            className="bk-fade-up"
            style={{ animationDelay: `${i * 80}ms` }}
          >
            <BranchCard
              branch={branch}
              onClick={() => navigate(`/owner/branch/${branch.branch_id}`)}
            />
          </div>
        ))}
        {revenue.branches.length === 0 && (
          <p className="py-8 text-center text-[var(--bk-text-secondary)]">Филиалы не найдены</p>
        )}
      </div>
    </div>
  )
}
