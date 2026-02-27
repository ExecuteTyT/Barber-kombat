import { useState, useEffect, useCallback } from 'react'

import api from '../../api/client'
import { MedalBadge, IconTarget, IconX } from '../../components/Icons'
import { ScoreBar, RatingDetail, formatMoney, formatDate } from '../../components/KombatComponents'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useKombatRating } from '../../hooks/useKombatRating'
import type { RatingEntry, RatingWeights, BarberStatsResponse } from '../../types'

function useBarberStats(barberId: string) {
  const [stats, setStats] = useState<BarberStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    api
      .get<BarberStatsResponse>(`/kombat/barber/${barberId}/stats`)
      .then(({ data }) => {
        if (!cancelled) {
          setStats(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError('Не удалось загрузить статистику')
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [barberId])

  return { stats, loading, error }
}

function BarberDetailModal({ barberId, onClose }: { barberId: string; onClose: () => void }) {
  const { stats, loading, error } = useBarberStats(barberId)

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative max-h-[85vh] w-full max-w-md overflow-hidden rounded-t-2xl bg-[var(--bk-bg)] sm:rounded-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--bk-border)] px-4 py-3">
          <h2 className="bk-heading text-lg">
            {loading ? 'Загрузка...' : (stats?.name ?? 'Барбер')}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-[var(--bk-text-secondary)] transition-colors hover:bg-[var(--bk-bg-elevated)]"
          >
            <IconX size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto p-4" style={{ maxHeight: 'calc(85vh - 56px)' }}>
          {loading && <LoadingSkeleton lines={6} />}

          {error && <p className="py-6 text-center text-[var(--bk-red)]">{error}</p>}

          {stats && (
            <>
              {/* Monthly summary */}
              <div className="mb-4">
                <h3 className="mb-3 text-sm font-medium text-[var(--bk-text-secondary)]">
                  Статистика за месяц
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <StatCard label="Побед" value={String(stats.wins)} />
                  <StatCard label="Ср. рейтинг" value={stats.avg_score.toFixed(1)} />
                  <StatCard label="Выручка" value={formatMoney(stats.total_revenue)} />
                  <StatCard
                    label="Ср. выручка/день"
                    value={formatMoney(stats.avg_revenue_per_day)}
                  />
                  <StatCard label="Ср. ЧС" value={stats.avg_cs.toFixed(2)} />
                  <StatCard label="Товары" value={`${stats.total_products} шт`} />
                  <StatCard label="Допы" value={`${stats.total_extras} шт`} />
                  <StatCard
                    label="Ср. отзыв"
                    value={stats.avg_review !== null ? stats.avg_review.toFixed(1) : '\u{2014}'}
                  />
                </div>
              </div>

              {/* Daily scores */}
              {stats.daily_scores.length > 0 && (
                <div>
                  <h3 className="mb-3 text-sm font-medium text-[var(--bk-text-secondary)]">
                    Результаты по дням
                  </h3>
                  <div className="space-y-1">
                    {stats.daily_scores.map((day) => (
                      <div
                        key={day.date}
                        className="flex items-center justify-between rounded-lg bg-[var(--bk-bg-elevated)] px-3 py-2.5"
                      >
                        <span className="text-sm text-[var(--bk-text)]">
                          {formatDate(day.date)}
                        </span>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-bold tabular-nums text-[var(--bk-text)]">
                            {day.score.toFixed(1)}
                          </span>
                          <MedalBadge rank={day.rank} size={22} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-[var(--bk-bg-elevated)] px-3 py-2.5">
      <p className="text-xs text-[var(--bk-text-secondary)]">{label}</p>
      <p className="mt-0.5 font-bold tabular-nums text-[var(--bk-text)]">{value}</p>
    </div>
  )
}

function ChefRatingRow({
  entry,
  weights,
  onDetail,
}: {
  entry: RatingEntry
  weights: RatingWeights
  onDetail: (barberId: string) => void
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{ order: entry.rank }}>
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <MedalBadge rank={entry.rank} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between">
            <span className="truncate font-medium text-[var(--bk-text)]">{entry.name}</span>
            <span
              className="ml-2 font-bold tabular-nums text-lg"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {entry.total_score.toFixed(1)}
            </span>
          </div>
          <ScoreBar entry={entry} weights={weights} />
        </div>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ${
          expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        <div className="overflow-hidden">
          {expanded && (
            <>
              <RatingDetail entry={entry} />
              <div className="px-4 pb-3">
                <button
                  type="button"
                  onClick={() => onDetail(entry.barber_id)}
                  className="w-full rounded-xl bg-[var(--bk-gold)]/10 py-2 text-sm font-semibold text-[var(--bk-gold)] transition-colors active:bg-[var(--bk-gold)]/20"
                >
                  Подробнее
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ChefKombatScreen() {
  const { todayRating, isLoading, error } = useKombatRating()
  const [detailBarberId, setDetailBarberId] = useState<string | null>(null)

  const handleCloseModal = useCallback(() => setDetailBarberId(null), [])

  if (isLoading && !todayRating) {
    return (
      <div className="p-4">
        <LoadingSkeleton lines={2} />
        <div className="mt-6 space-y-4">
          {Array.from({ length: 4 }, (_, i) => (
            <LoadingSkeleton key={i} lines={2} />
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

  if (!todayRating) return null

  const { ratings, prize_fund, plan, weights, date, branch_name, is_active } = todayRating

  return (
    <div className="pb-4">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <h1 className="bk-heading text-xl">{branch_name}</h1>
          <p className="mt-0.5 text-sm text-[var(--bk-text-secondary)]">{formatDate(date)}</p>
        </div>
        {is_active && (
          <span className="bk-live-pulse flex items-center gap-1.5 rounded-full bg-[var(--bk-red)]/10 px-3 py-1.5 text-xs font-bold tracking-wider text-[var(--bk-red)]">
            <span className="inline-block h-2 w-2 rounded-full bg-[var(--bk-red)]" />
            LIVE
          </span>
        )}
      </div>

      {/* Rating list */}
      <div className="mt-2 space-y-1 px-2">
        {ratings.map((entry) => (
          <ChefRatingRow
            key={entry.barber_id}
            entry={entry}
            weights={weights}
            onDetail={setDetailBarberId}
          />
        ))}
        {ratings.length === 0 && (
          <p className="px-4 py-8 text-center text-[var(--bk-text-secondary)]">
            Данных за сегодня пока нет
          </p>
        )}
      </div>

      {/* Prize fund */}
      <div className="mx-4 mt-5">
        <div className="grid grid-cols-3 gap-2">
          {[
            { rank: 1, amount: prize_fund.gold },
            { rank: 2, amount: prize_fund.silver },
            { rank: 3, amount: prize_fund.bronze },
          ].map((p) => (
            <div key={p.rank} className="bk-card flex flex-col items-center px-2 py-3">
              <MedalBadge rank={p.rank} size={32} />
              <span className="mt-2 text-sm font-bold tabular-nums text-[var(--bk-text)]">
                {formatMoney(p.amount)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-2 text-center text-xs text-[var(--bk-text-dim)]">
          Призовой фонд с 1-го числа
        </p>
      </div>

      {/* Plan progress */}
      {plan && (
        <div className="bk-card mx-4 mt-4 p-4">
          <div className="flex items-center gap-2">
            <IconTarget size={16} className="text-[var(--bk-gold)]" />
            <span className="text-sm font-medium text-[var(--bk-text)]">План филиала</span>
            <span
              className="ml-auto font-bold tabular-nums text-lg"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {plan.percentage.toFixed(0)}%
            </span>
          </div>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
            <div
              className="bk-progress-fill h-full transition-all duration-700"
              style={{ width: `${Math.min(plan.percentage, 100)}%` }}
            />
          </div>
          <p className="mt-2 text-sm tabular-nums text-[var(--bk-text-secondary)]">
            {formatMoney(plan.current)} из {formatMoney(plan.target)}
          </p>
          {plan.required_daily > 0 && (
            <p className="mt-0.5 text-xs text-[var(--bk-text-dim)]">
              Нужно ~{formatMoney(plan.required_daily)}/смену
            </p>
          )}
        </div>
      )}

      {/* Barber detail modal */}
      {detailBarberId && <BarberDetailModal barberId={detailBarberId} onClose={handleCloseModal} />}
    </div>
  )
}
