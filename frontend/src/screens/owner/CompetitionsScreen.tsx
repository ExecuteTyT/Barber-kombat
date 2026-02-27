import { useEffect, useState, useCallback, useMemo } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useKombatStore } from '../../stores/kombatStore'
import { useOwnerStore } from '../../stores/ownerStore'
import { usePvrStore } from '../../stores/pvrStore'
import type { RatingEntry, RatingWeights, BarberPVRResponse, WSMessage } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

const RANK_MEDALS = ['', '\u{1F947}', '\u{1F948}', '\u{1F949}'] as const

type Tab = 'kombat' | 'pvr'

// --- Compact rating row for owner view ---
function RatingRow({ entry, weights }: { entry: RatingEntry; weights: RatingWeights }) {
  const medal = entry.rank <= 3 ? RANK_MEDALS[entry.rank] : ''
  const segments = [
    { weight: weights.revenue, color: 'bg-blue-500', score: entry.revenue_score },
    { weight: weights.cs, color: 'bg-emerald-500', score: entry.cs_score },
    { weight: weights.products, color: 'bg-amber-500', score: entry.products_score },
    { weight: weights.extras, color: 'bg-purple-500', score: entry.extras_score },
    { weight: weights.reviews, color: 'bg-rose-500', score: entry.reviews_score },
  ]

  return (
    <div className="flex items-center gap-2 px-3 py-2">
      <span className="w-7 text-center text-sm font-bold">{medal || entry.rank}</span>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between">
          <span className="truncate text-sm font-medium">{entry.name}</span>
          <span className="ml-1 font-bold tabular-nums">{entry.total_score.toFixed(1)}</span>
        </div>
        <div className="mt-0.5 flex h-1 gap-px overflow-hidden rounded-full">
          {segments.map((s, i) => (
            <div
              key={i}
              className={`${s.color}`}
              style={{ width: `${s.weight}%`, opacity: s.score > 0 ? 1 : 0.2 }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// --- PVR barber row ---
function PVRRow({ barber }: { barber: BarberPVRResponse }) {
  return (
    <div className="flex items-center justify-between px-3 py-2">
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium">{barber.name}</span>
        {barber.thresholds_reached.length > 0 && (
          <span className="ml-1.5 text-xs text-emerald-500">
            {'\u{2705}'}
            {barber.thresholds_reached.length}
          </span>
        )}
      </div>
      <div className="text-right">
        <span className="font-bold tabular-nums text-sm">
          {formatMoney(barber.cumulative_revenue)}
        </span>
        {barber.bonus_amount > 0 && (
          <p className="text-xs text-emerald-500">+{formatMoney(barber.bonus_amount)}</p>
        )}
      </div>
    </div>
  )
}

export default function CompetitionsScreen() {
  const [tab, setTab] = useState<Tab>('kombat')
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null)

  // Dashboard for branch list
  const { revenue, fetchDashboard } = useOwnerStore()
  // Kombat
  const { todayRating, fetchTodayRating, applyRatingUpdate } = useKombatStore()
  // PVR
  const { branchPvr, fetchBranchPvr, fetchThresholds } = usePvrStore()

  const branches = useMemo(() => revenue?.branches ?? [], [revenue])

  // Load branch list
  useEffect(() => {
    if (!revenue) fetchDashboard()
  }, [revenue, fetchDashboard])

  // Auto-select first branch (adjusting state during render)
  if (branches.length > 0 && !selectedBranchId) {
    setSelectedBranchId(branches[0].branch_id)
  }

  // Fetch data when branch changes
  useEffect(() => {
    if (!selectedBranchId) return
    if (tab === 'kombat') {
      fetchTodayRating(selectedBranchId)
    } else {
      fetchBranchPvr(selectedBranchId)
      fetchThresholds()
    }
  }, [selectedBranchId, tab, fetchTodayRating, fetchBranchPvr, fetchThresholds])

  // WebSocket for real-time
  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      if (message.type === 'rating_update') {
        const data = message.data as { branch_id?: string; ratings?: RatingEntry[] }
        if (data.branch_id === selectedBranchId && data.ratings) {
          applyRatingUpdate(data.ratings)
        }
      }
    },
    [selectedBranchId, applyRatingUpdate],
  )
  useWebSocket(handleWSMessage)

  return (
    <div className="pb-4 pt-4">
      <h1 className="px-4 text-lg font-bold">Соревнования</h1>

      {/* Tabs */}
      <div className="mx-4 mt-3 flex gap-2">
        {[
          { key: 'kombat' as Tab, label: 'Barber Kombat' },
          { key: 'pvr' as Tab, label: 'ПВР' },
        ].map((t) => (
          <button
            key={t.key}
            type="button"
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                : 'bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)]'
            }`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Branch selector */}
      <div className="mx-4 mt-3">
        <select
          className="w-full rounded-xl border border-[var(--tg-theme-hint-color)]/20 bg-[var(--tg-theme-secondary-bg-color)] px-3 py-2.5 text-sm text-[var(--tg-theme-text-color)]"
          value={selectedBranchId ?? ''}
          onChange={(e) => setSelectedBranchId(e.target.value)}
        >
          {branches.map((b) => (
            <option key={b.branch_id} value={b.branch_id}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      {/* Content */}
      <div className="mx-4 mt-3">
        {tab === 'kombat' &&
          (todayRating ? (
            <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]">
              {/* Header */}
              <div className="flex items-center justify-between px-3 pb-1 pt-3">
                <span className="text-sm font-medium">{todayRating.branch_name}</span>
                {todayRating.is_active && (
                  <span className="flex items-center gap-1 text-xs text-red-500">
                    <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-red-500" />
                    LIVE
                  </span>
                )}
              </div>
              {/* Ratings */}
              <div className="divide-y divide-[var(--tg-theme-hint-color)]/10">
                {todayRating.ratings.map((r) => (
                  <RatingRow key={r.barber_id} entry={r} weights={todayRating.weights} />
                ))}
              </div>
              {todayRating.ratings.length === 0 && (
                <p className="p-4 text-center text-sm text-[var(--tg-theme-hint-color)]">
                  Данных за сегодня нет
                </p>
              )}
              {/* Prize fund */}
              <div className="flex justify-center gap-3 border-t border-[var(--tg-theme-hint-color)]/10 px-3 py-2">
                {[
                  { m: '\u{1F947}', v: todayRating.prize_fund.gold },
                  { m: '\u{1F948}', v: todayRating.prize_fund.silver },
                  { m: '\u{1F949}', v: todayRating.prize_fund.bronze },
                ].map((p) => (
                  <span key={p.m} className="text-xs tabular-nums">
                    {p.m} {formatMoney(p.v)}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <LoadingSkeleton lines={6} />
          ))}

        {tab === 'pvr' &&
          (branchPvr ? (
            <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]">
              <div className="px-3 pb-1 pt-3">
                <span className="text-sm font-medium">
                  ПВР \u{2022} {branchPvr.month}
                </span>
              </div>
              <div className="divide-y divide-[var(--tg-theme-hint-color)]/10">
                {[...branchPvr.barbers]
                  .sort((a, b) => b.cumulative_revenue - a.cumulative_revenue)
                  .map((b) => (
                    <PVRRow key={b.barber_id} barber={b} />
                  ))}
              </div>
              {branchPvr.barbers.length === 0 && (
                <p className="p-4 text-center text-sm text-[var(--tg-theme-hint-color)]">
                  Нет данных ПВР
                </p>
              )}
            </div>
          ) : (
            <LoadingSkeleton lines={6} />
          ))}
      </div>
    </div>
  )
}
