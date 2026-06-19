import Button from './Button'
import ReviewCard from './ReviewCard'
import { IconStar } from './Icons'
import type { ReviewResponse } from '../types'

export type ReviewFilterTab = 'all' | 'negative' | 'unprocessed'

/** Tabs + review cards + empty/load-more states. Shared by owner and admin. */
export default function ReviewsList({
  reviews,
  total,
  activeTab,
  onTabChange,
  onProcess,
  unprocessedCount,
  onLoadMore,
  isLoadingMore,
}: {
  reviews: ReviewResponse[]
  total: number
  activeTab: ReviewFilterTab
  onTabChange: (tab: ReviewFilterTab) => void
  onProcess: (review: ReviewResponse) => void
  unprocessedCount: number
  onLoadMore?: () => void
  isLoadingMore?: boolean
}) {
  const tabs: { key: ReviewFilterTab; label: string; badge?: number }[] = [
    { key: 'all', label: 'Все' },
    { key: 'negative', label: 'Негативные' },
    { key: 'unprocessed', label: 'Необработанные', badge: unprocessedCount },
  ]

  return (
    <div>
      <div className="flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`flex min-h-[40px] items-center gap-1 rounded-lg px-3 py-2 text-xs font-semibold transition-colors ${
              activeTab === t.key
                ? 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]'
                : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]'
            }`}
            onClick={() => onTabChange(t.key)}
          >
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--bk-red)] px-1 text-[10px] font-bold text-white">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="mt-3 space-y-2">
        {reviews.map((r) => (
          <ReviewCard key={r.id} review={r} onProcess={onProcess} />
        ))}

        {reviews.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <IconStar size={28} className="text-[var(--bk-text-dim)]" />
            <p className="text-sm text-[var(--bk-text-secondary)]">Отзывов пока нет</p>
          </div>
        )}

        {onLoadMore && reviews.length > 0 && reviews.length < total && (
          <Button
            variant="secondary"
            className="w-full"
            onClick={onLoadMore}
            disabled={isLoadingMore}
          >
            {isLoadingMore ? 'Загрузка...' : `Показать ещё (${total - reviews.length})`}
          </Button>
        )}
      </div>
    </div>
  )
}
