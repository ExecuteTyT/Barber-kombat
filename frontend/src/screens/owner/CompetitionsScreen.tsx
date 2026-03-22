import { useEffect, useState, useCallback, useMemo } from 'react'

import { MedalBadge } from '../../components/Icons'
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

const SEGMENT_COLORS = [
  'bg-[var(--bk-score-revenue)]',
  'bg-[var(--bk-score-cs)]',
  'bg-[var(--bk-score-products)]',
  'bg-[var(--bk-score-extras)]',
  'bg-[var(--bk-score-reviews)]',
]

const SEGMENT_LABELS = ['Выручка', 'Ср. чек', 'Товары', 'Доп. услуги', 'Отзывы']

type Tab = 'kombat' | 'pvr'

function RatingRow({ entry, weights }: { entry: RatingEntry; weights: RatingWeights }) {
  const segments = [
    { weight: weights.revenue, score: entry.revenue_score },
    { weight: weights.cs, score: entry.cs_score },
    { weight: weights.products, score: entry.products_score },
    { weight: weights.extras, score: entry.extras_score },
    { weight: weights.reviews, score: entry.reviews_score },
  ]

  return (
    <div className="flex items-center gap-2 px-3 py-2.5">
      <MedalBadge rank={entry.rank} size={24} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between">
          <span className="truncate text-sm font-medium text-[var(--bk-text)]">{entry.name}</span>
          <div className="ml-1 flex items-baseline gap-2">
            <span className="text-xs tabular-nums text-[var(--bk-text-secondary)]">
              {formatMoney(entry.revenue)}
            </span>
            <span className="font-bold tabular-nums text-[var(--bk-text)]">
              {entry.total_score.toFixed(1)}
            </span>
          </div>
        </div>
        <div className="mt-0.5 flex h-1 gap-px overflow-hidden rounded-full">
          {segments.map((s, i) => (
            <div
              key={i}
              className={SEGMENT_COLORS[i]}
              style={{ width: `${s.weight}%`, opacity: s.score > 0 ? 1 : 0.15 }}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

function PVRRow({ barber }: { barber: BarberPVRResponse }) {
  return (
    <div className="px-3 py-2.5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--bk-text)]">{barber.name}</span>
        <span className="text-sm font-bold tabular-nums text-[var(--bk-text)]">
          {formatMoney(barber.cumulative_revenue)}
        </span>
      </div>
      {barber.bonus_amount > 0 && (
        <div className="mt-1 flex items-center justify-between">
          <span className="text-xs text-[var(--bk-text-dim)]">
            Достигнут порог {formatMoney(barber.thresholds_reached[barber.thresholds_reached.length - 1]?.amount ?? 0)}
          </span>
          <span className="text-xs font-semibold text-[var(--bk-gold)]">
            Премия: +{formatMoney(barber.bonus_amount)}
          </span>
        </div>
      )}
      {barber.bonus_amount === 0 && barber.next_threshold && barber.remaining_to_next !== null && (
        <div className="mt-1">
          <span className="text-xs text-[var(--bk-text-dim)]">
            До премии ещё {formatMoney(barber.remaining_to_next)}
          </span>
        </div>
      )}
    </div>
  )
}

export default function CompetitionsScreen() {
  const [tab, setTab] = useState<Tab>('kombat')
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null)

  const { revenue, fetchDashboard } = useOwnerStore()
  const { todayRating, fetchTodayRating, applyRatingUpdate } = useKombatStore()
  const { branchPvr, fetchBranchPvr, fetchThresholds } = usePvrStore()

  const branches = useMemo(() => revenue?.branches ?? [], [revenue])

  useEffect(() => {
    if (!revenue) fetchDashboard()
  }, [revenue, fetchDashboard])

  if (branches.length > 0 && !selectedBranchId) {
    setSelectedBranchId(branches[0].branch_id)
  }

  useEffect(() => {
    if (!selectedBranchId) return
    if (tab === 'kombat') {
      fetchTodayRating(selectedBranchId)
    } else {
      fetchBranchPvr(selectedBranchId)
      fetchThresholds()
    }
  }, [selectedBranchId, tab, fetchTodayRating, fetchBranchPvr, fetchThresholds])

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
      <h1 className="bk-heading px-4 text-xl">Рейтинг и премии</h1>

      {/* Tabs */}
      <div className="mx-4 mt-3 flex gap-2">
        {[
          { key: 'kombat' as Tab, label: 'Рейтинг дня' },
          { key: 'pvr' as Tab, label: 'Премии' },
        ].map((t) => (
          <button
            key={t.key}
            type="button"
            className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition-colors ${
              tab === t.key
                ? 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]'
                : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]'
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
          className="w-full rounded-xl border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-3 py-2.5 text-sm text-[var(--bk-text)]"
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
            <div className="bk-card overflow-hidden">
              <div className="flex items-center justify-between px-3 pb-1 pt-3">
                <span className="text-sm font-medium text-[var(--bk-text)]">
                  {todayRating.branch_name}
                </span>
                {todayRating.is_active && (
                  <span className="flex items-center gap-1 text-xs font-bold text-[var(--bk-red)]">
                    <span className="bk-live-pulse inline-block h-1.5 w-1.5 rounded-full bg-[var(--bk-red)]" />
                    LIVE
                  </span>
                )}
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-x-3 gap-y-1 px-3 pb-2">
                {SEGMENT_LABELS.map((label, i) => (
                  <span key={label} className="flex items-center gap-1 text-[10px] text-[var(--bk-text-dim)]">
                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${SEGMENT_COLORS[i]}`} />
                    {label}
                  </span>
                ))}
              </div>

              <div className="divide-y divide-[var(--bk-border)]">
                {todayRating.ratings.map((r) => (
                  <RatingRow key={r.barber_id} entry={r} weights={todayRating.weights} />
                ))}
              </div>
              {todayRating.ratings.length === 0 && (
                <p className="p-4 text-center text-sm text-[var(--bk-text-secondary)]">
                  Данных за сегодня нет
                </p>
              )}

              {/* Explanation */}
              <div className="border-t border-[var(--bk-border)] px-3 py-2">
                <p className="text-[10px] leading-relaxed text-[var(--bk-text-dim)]">
                  Баллы (макс. 100) складываются из 5 показателей. Лучший по каждому получает максимум, остальные — пропорционально.
                </p>
              </div>

              {/* Prize fund */}
              <div className="flex justify-center gap-4 border-t border-[var(--bk-border)] px-3 py-2">
                <span className="text-[10px] text-[var(--bk-text-dim)]">Призы за день:</span>
                {[
                  { rank: 1, v: todayRating.prize_fund.gold },
                  { rank: 2, v: todayRating.prize_fund.silver },
                  { rank: 3, v: todayRating.prize_fund.bronze },
                ].map((p) => (
                  <span
                    key={p.rank}
                    className="flex items-center gap-1.5 text-xs tabular-nums text-[var(--bk-text-secondary)]"
                  >
                    <MedalBadge rank={p.rank} size={20} />
                    {formatMoney(p.v)}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <LoadingSkeleton lines={6} />
          ))}

        {tab === 'pvr' &&
          (branchPvr ? (
            <div className="bk-card overflow-hidden">
              <div className="px-3 pb-1 pt-3">
                <span className="text-sm font-medium text-[var(--bk-text)]">
                  Выручка и премии за{' '}
                  {new Date(branchPvr.month + '-01').toLocaleDateString('ru-RU', {
                    month: 'long',
                    year: 'numeric',
                  })}
                </span>
                <p className="mt-0.5 text-[10px] leading-relaxed text-[var(--bk-text-dim)]">
                  Накопительная выручка каждого барбера с 1-го числа. При достижении порога начисляется премия.
                </p>
              </div>
              <div className="divide-y divide-[var(--bk-border)]">
                {[...branchPvr.barbers]
                  .sort((a, b) => b.cumulative_revenue - a.cumulative_revenue)
                  .map((b) => (
                    <PVRRow key={b.barber_id} barber={b} />
                  ))}
              </div>
              {branchPvr.barbers.length === 0 && (
                <p className="p-4 text-center text-sm text-[var(--bk-text-secondary)]">
                  Нет данных по премиям
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
