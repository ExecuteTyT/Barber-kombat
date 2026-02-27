import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

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
      className="w-full rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4 text-left active:opacity-80"
      onClick={onClick}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium">{branch.name}</span>
        <span className="text-sm text-[var(--tg-theme-hint-color)]">
          {branch.barbers_in_shift}/{branch.barbers_total} {'\u{1F464}'}
        </span>
      </div>

      <p className="mt-1 text-lg font-bold tabular-nums">
        {formatMoney(branch.revenue_today)}{' '}
        <span className="text-sm font-normal text-[var(--tg-theme-hint-color)]">сегодня</span>
      </p>

      {/* Plan progress */}
      <div className="mt-2">
        <div className="h-2 overflow-hidden rounded-full bg-[var(--tg-theme-bg-color)]">
          <div
            className="h-full rounded-full bg-[var(--tg-theme-button-color)] transition-all duration-700"
            style={{ width: `${Math.min(branch.plan_percentage, 100)}%` }}
          />
        </div>
        <div className="mt-1 flex items-baseline justify-between text-xs">
          <span className="text-[var(--tg-theme-hint-color)]">
            {formatMoney(branch.revenue_mtd)} / {formatMoney(branch.plan_target)}
          </span>
          <span className="font-bold tabular-nums">{branch.plan_percentage.toFixed(0)}% плана</span>
        </div>
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
        <p className="text-[var(--tg-theme-destructive-text-color)]">{error}</p>
      </div>
    )
  }

  if (!revenue) return null

  return (
    <div className="pb-4 pt-4">
      {/* Network header */}
      <div className="px-4">
        <h1 className="text-lg font-bold">Дашборд</h1>
        <div className="mt-2 flex gap-4">
          <div>
            <p className="text-xs text-[var(--tg-theme-hint-color)]">Сегодня</p>
            <p className="text-xl font-bold tabular-nums">
              {formatMoney(revenue.network_total_today)}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--tg-theme-hint-color)]">С начала месяца</p>
            <p className="text-xl font-bold tabular-nums">
              {formatMoney(revenue.network_total_mtd)}
            </p>
          </div>
        </div>
        {alarumTotal > 0 && (
          <div className="mt-2 flex items-center gap-1.5 text-sm text-red-500">
            <span className="inline-block h-2 w-2 rounded-full bg-red-500" />
            {alarumTotal} необработанн{alarumTotal === 1 ? 'ый' : 'ых'} отзыв
            {alarumTotal === 1 ? '' : alarumTotal < 5 ? 'а' : 'ов'}
          </div>
        )}
      </div>

      {/* Branch cards */}
      <div className="mx-4 mt-4 space-y-3">
        {revenue.branches.map((branch) => (
          <BranchCard
            key={branch.branch_id}
            branch={branch}
            onClick={() => navigate(`/owner/branch/${branch.branch_id}`)}
          />
        ))}
        {revenue.branches.length === 0 && (
          <p className="py-8 text-center text-[var(--tg-theme-hint-color)]">Филиалы не найдены</p>
        )}
      </div>
    </div>
  )
}
