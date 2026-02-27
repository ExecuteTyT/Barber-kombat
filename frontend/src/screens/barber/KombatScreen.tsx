import { useState } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useKombatRating } from '../../hooks/useKombatRating'
import { useAuthStore } from '../../stores/authStore'
import type { RatingEntry, RatingWeights } from '../../types'

const RANK_MEDALS = ['', '\u{1F947}', '\u{1F948}', '\u{1F949}'] as const

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
  })
}

// Score bar segments showing contribution of each parameter
function ScoreBar({ entry, weights }: { entry: RatingEntry; weights: RatingWeights }) {
  const segments = [
    { score: entry.revenue_score, weight: weights.revenue, color: 'bg-blue-500' },
    { score: entry.cs_score, weight: weights.cs, color: 'bg-emerald-500' },
    { score: entry.products_score, weight: weights.products, color: 'bg-amber-500' },
    { score: entry.extras_score, weight: weights.extras, color: 'bg-purple-500' },
    { score: entry.reviews_score, weight: weights.reviews, color: 'bg-rose-500' },
  ]

  return (
    <div className="mt-1 flex h-1.5 gap-px overflow-hidden rounded-full">
      {segments.map((seg, i) => (
        <div
          key={i}
          className={`${seg.color} transition-all duration-500`}
          style={{ width: `${seg.weight}%`, opacity: seg.score > 0 ? 1 : 0.2 }}
        />
      ))}
    </div>
  )
}

// Expandable detail card for a barber
function RatingDetail({ entry }: { entry: RatingEntry }) {
  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2 px-4 pb-3 pt-1 text-sm text-[var(--tg-theme-hint-color)]">
      <div>
        <span className="text-[var(--tg-theme-text-color)]">{formatMoney(entry.revenue)}</span>
        <span className="ml-1">Выручка</span>
      </div>
      <div>
        <span className="text-[var(--tg-theme-text-color)]">{entry.cs_value.toFixed(2)}</span>
        <span className="ml-1">ЧС</span>
      </div>
      <div>
        <span className="text-[var(--tg-theme-text-color)]">{entry.products_count}</span>
        <span className="ml-1">шт Товары</span>
      </div>
      <div>
        <span className="text-[var(--tg-theme-text-color)]">{entry.extras_count}</span>
        <span className="ml-1">шт Допы</span>
      </div>
      <div>
        <span className="text-[var(--tg-theme-text-color)]">
          {entry.reviews_avg !== null ? entry.reviews_avg.toFixed(1) : '\u{2014}'}
        </span>
        <span className="ml-1">Отзывы</span>
      </div>
    </div>
  )
}

function RatingRow({
  entry,
  weights,
  isCurrentUser,
}: {
  entry: RatingEntry
  weights: RatingWeights
  isCurrentUser: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const medal = entry.rank <= 3 ? RANK_MEDALS[entry.rank] : ''

  return (
    <div
      className={`transition-all duration-300 ${
        isCurrentUser
          ? 'rounded-xl bg-[var(--tg-theme-button-color)]/10'
          : ''
      }`}
      style={{
        // LayoutId-style animation: rank drives order
        order: entry.rank,
      }}
    >
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Rank */}
        <span className="w-8 text-center text-lg font-bold">
          {medal || entry.rank}
        </span>

        {/* Name + score bar */}
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between">
            <span
              className={`truncate font-medium ${
                isCurrentUser ? 'text-[var(--tg-theme-button-color)]' : ''
              }`}
            >
              {entry.name}
            </span>
            <span className="ml-2 text-lg font-bold tabular-nums">
              {entry.total_score.toFixed(1)}
            </span>
          </div>
          <ScoreBar entry={entry} weights={weights} />
        </div>
      </button>

      {/* Expanded details */}
      <div
        className={`grid transition-[grid-template-rows] duration-200 ${
          expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        <div className="overflow-hidden">
          {expanded && <RatingDetail entry={entry} />}
        </div>
      </div>
    </div>
  )
}

export default function KombatScreen() {
  const { todayRating, isLoading, error } = useKombatRating()
  const user = useAuthStore((s) => s.user)

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
        <p className="text-[var(--tg-theme-destructive-text-color)]">{error}</p>
      </div>
    )
  }

  if (!todayRating) return null

  const { ratings, prize_fund, plan, weights, date, branch_name, is_active } =
    todayRating

  return (
    <div className="pb-4">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <h1 className="text-lg font-bold">{branch_name}</h1>
          <p className="text-sm text-[var(--tg-theme-hint-color)]">
            {formatDate(date)}
          </p>
        </div>
        {is_active && (
          <span className="flex items-center gap-1 rounded-full bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-500">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" />
            LIVE
          </span>
        )}
      </div>

      {/* Rating table */}
      <div className="mt-2">
        {ratings.map((entry) => (
          <RatingRow
            key={entry.barber_id}
            entry={entry}
            weights={weights}
            isCurrentUser={entry.barber_id === user?.id}
          />
        ))}
        {ratings.length === 0 && (
          <p className="px-4 py-8 text-center text-[var(--tg-theme-hint-color)]">
            Данных за сегодня пока нет
          </p>
        )}
      </div>

      {/* Prize fund */}
      <div className="mx-4 mt-4">
        <div className="grid grid-cols-3 gap-2">
          {[
            { medal: '\u{1F947}', amount: prize_fund.gold },
            { medal: '\u{1F948}', amount: prize_fund.silver },
            { medal: '\u{1F949}', amount: prize_fund.bronze },
          ].map((p) => (
            <div
              key={p.medal}
              className="flex flex-col items-center rounded-xl bg-[var(--tg-theme-secondary-bg-color)] px-2 py-3"
            >
              <span className="text-xl">{p.medal}</span>
              <span className="mt-1 text-sm font-bold tabular-nums">
                {formatMoney(p.amount)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-1.5 text-center text-xs text-[var(--tg-theme-hint-color)]">
          Призовой фонд с 1-го числа
        </p>
      </div>

      {/* Plan progress */}
      {plan && (
        <div className="mx-4 mt-4 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4">
          <div className="flex items-baseline justify-between">
            <span className="text-sm font-medium">План филиала</span>
            <span className="text-lg font-bold tabular-nums">
              {plan.percentage.toFixed(0)}%
            </span>
          </div>
          {/* Progress bar */}
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-[var(--tg-theme-bg-color)]">
            <div
              className="h-full rounded-full bg-[var(--tg-theme-button-color)] transition-all duration-700"
              style={{ width: `${Math.min(plan.percentage, 100)}%` }}
            />
          </div>
          <p className="mt-2 text-sm tabular-nums text-[var(--tg-theme-hint-color)]">
            {formatMoney(plan.current)} из {formatMoney(plan.target)}
          </p>
          {plan.required_daily > 0 && (
            <p className="mt-0.5 text-xs text-[var(--tg-theme-hint-color)]">
              Нужно ~{formatMoney(plan.required_daily)}/смену
            </p>
          )}
        </div>
      )}
    </div>
  )
}
