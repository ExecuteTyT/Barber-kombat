/* eslint-disable react-refresh/only-export-components */
import type { RatingEntry, RatingWeights } from '../types'

export function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

export function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
  })
}

export const SEGMENT_COLORS = [
  'bg-[var(--bk-score-revenue)]',
  'bg-[var(--bk-score-cs)]',
  'bg-[var(--bk-score-products)]',
  'bg-[var(--bk-score-extras)]',
  'bg-[var(--bk-score-reviews)]',
]

export function ScoreBar({ entry, weights }: { entry: RatingEntry; weights: RatingWeights }) {
  const segments = [
    { score: entry.revenue_score, weight: weights.revenue },
    { score: entry.cs_score, weight: weights.cs },
    { score: entry.products_score, weight: weights.products },
    { score: entry.extras_score, weight: weights.extras },
    { score: entry.reviews_score, weight: weights.reviews },
  ]

  return (
    <div className="mt-1.5 flex h-1.5 gap-px overflow-hidden rounded-full">
      {segments.map((seg, i) => (
        <div
          key={i}
          className={`${SEGMENT_COLORS[i]} transition-all duration-500`}
          style={{ width: `${seg.weight}%`, opacity: seg.score > 0 ? 1 : 0.15 }}
        />
      ))}
    </div>
  )
}

export function RatingDetail({ entry }: { entry: RatingEntry }) {
  const metrics = [
    { label: 'Выручка', value: formatMoney(entry.revenue) },
    { label: 'ЧС', value: entry.cs_value.toFixed(2) },
    { label: 'Товары', value: `${entry.products_count} шт` },
    { label: 'Допы', value: `${entry.extras_count} шт` },
    {
      label: 'Отзывы',
      value: entry.reviews_avg !== null ? entry.reviews_avg.toFixed(1) : '\u{2014}',
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--bk-border)] px-4 pb-3 pt-3 text-sm">
      {metrics.map((m) => (
        <div key={m.label} className="flex items-baseline justify-between">
          <span className="text-[var(--bk-text-secondary)]">{m.label}</span>
          <span className="font-semibold tabular-nums text-[var(--bk-text)]">{m.value}</span>
        </div>
      ))}
    </div>
  )
}
