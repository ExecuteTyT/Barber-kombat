import { useEffect } from 'react'

import { IconCheck } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAuthStore } from '../../stores/authStore'
import { usePvrStore } from '../../stores/pvrStore'
import type { BarberPVRResponse, PVRThreshold } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function formatMoneyShort(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  if (rubles >= 1000) {
    return (rubles / 1000).toFixed(rubles % 1000 === 0 ? 0 : 1) + '\u{00A0}тыс'
  }
  return String(rubles)
}

function BarberPVRCard({
  barber,
  thresholds,
}: {
  barber: BarberPVRResponse
  thresholds: PVRThreshold[]
}) {
  const sorted = [...thresholds].sort((a, b) => a.amount - b.amount)
  const maxAmount = sorted.length > 0 ? sorted[sorted.length - 1].amount : 1
  const pct = Math.min((barber.cumulative_revenue / maxAmount) * 100, 100)

  return (
    <div className="bk-card p-4">
      <div className="flex items-baseline justify-between">
        <span className="font-medium text-[var(--bk-text)]">{barber.name}</span>
        <span
          className="text-lg font-bold tabular-nums"
          style={{ fontFamily: 'var(--bk-font-heading)' }}
        >
          {formatMoney(barber.cumulative_revenue)}
        </span>
      </div>

      <div className="relative mt-3">
        <div className="h-3 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
          <div
            className="bk-progress-fill h-full transition-all duration-700"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="relative mt-1">
          {sorted.map((t) => {
            const pos = (t.amount / maxAmount) * 100
            const reached = barber.cumulative_revenue >= t.amount
            return (
              <div
                key={t.amount}
                className="absolute -top-4 flex flex-col items-center"
                style={{ left: `${pos}%`, transform: 'translateX(-50%)' }}
              >
                <div
                  className={`h-2 w-0.5 ${
                    reached ? 'bg-[var(--bk-gold)]' : 'bg-[var(--bk-text-dim)]/30'
                  }`}
                />
              </div>
            )
          })}
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-[var(--bk-text-dim)]">
          <span>0</span>
          {sorted.length > 0 && <span>{formatMoneyShort(sorted[sorted.length - 1].amount)}</span>}
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between text-xs">
        {barber.bonus_amount > 0 ? (
          <span className="font-semibold text-[var(--bk-gold)]">
            Премия: {formatMoney(barber.bonus_amount)}
          </span>
        ) : (
          <span className="text-[var(--bk-text-dim)]">Премия: 0</span>
        )}
        {barber.next_threshold && barber.remaining_to_next !== null ? (
          <span className="text-[var(--bk-text-secondary)]">
            До {formatMoney(barber.next_threshold)}: {formatMoney(barber.remaining_to_next)}
          </span>
        ) : barber.current_threshold ? (
          <span className="font-semibold text-[var(--bk-green)]">Макс. порог достигнут</span>
        ) : null}
      </div>

      {barber.thresholds_reached.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {barber.thresholds_reached.map((t) => (
            <span
              key={t.amount}
              className="flex items-center gap-0.5 rounded bg-[var(--bk-gold)]/10 px-1.5 py-0.5 text-[10px] font-semibold text-[var(--bk-gold)]"
            >
              <IconCheck size={10} />
              {formatMoneyShort(t.amount)}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChefPVRScreen() {
  const user = useAuthStore((s) => s.user)
  const branchId = user?.branch_id
  const { branchPvr, thresholds, isLoading, error, fetchBranchPvr, fetchThresholds } = usePvrStore()

  useEffect(() => {
    if (branchId) {
      fetchBranchPvr(branchId)
      fetchThresholds()
    }
  }, [branchId, fetchBranchPvr, fetchThresholds])

  if (isLoading && !branchPvr) {
    return (
      <div className="p-4">
        <LoadingSkeleton lines={6} />
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

  if (!branchId) {
    return <div className="p-8 text-center text-[var(--bk-text-secondary)]">Филиал не назначен</div>
  }

  const barbers = branchPvr?.barbers ?? []
  const sorted = [...barbers].sort((a, b) => b.cumulative_revenue - a.cumulative_revenue)

  return (
    <div className="pb-4 pt-4">
      <h1 className="bk-heading px-4 text-xl">Премии за выручку</h1>
      {branchPvr && (
        <p className="mt-1 px-4 text-sm text-[var(--bk-text-secondary)]">{branchPvr.month}</p>
      )}

      <div className="mx-4 mt-4 space-y-3">
        {sorted.map((b) => (
          <BarberPVRCard key={b.barber_id} barber={b} thresholds={thresholds} />
        ))}
        {sorted.length === 0 && (
          <p className="py-8 text-center text-[var(--bk-text-secondary)]">Нет данных по премиям</p>
        )}
      </div>
    </div>
  )
}
