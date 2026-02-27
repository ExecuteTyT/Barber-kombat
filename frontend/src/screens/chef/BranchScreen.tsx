import { useEffect, useState, useCallback } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useAuthStore } from '../../stores/authStore'
import { useKombatStore } from '../../stores/kombatStore'
import { usePvrStore } from '../../stores/pvrStore'
import { useReviewsStore } from '../../stores/reviewsStore'
import ReviewProcessModal from './ReviewProcessModal'
import type {
  BarberPVRResponse,
  ReviewResponse,
  ReviewStatus,
  WSMessage,
} from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

// --- Today stats block ---
function TodayStats({
  revenueToday,
  revenueMonth,
  planPercentage,
  planTarget,
  barbersInShift,
  barbersTotal,
}: {
  revenueToday: number
  revenueMonth: number
  planPercentage: number
  planTarget: number
  barbersInShift: number
  barbersTotal: number
}) {
  return (
    <div className="mx-4 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-[var(--tg-theme-hint-color)]">Выручка дня</p>
          <p className="text-lg font-bold tabular-nums">{formatMoney(revenueToday)}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--tg-theme-hint-color)]">Выручка месяца</p>
          <p className="text-lg font-bold tabular-nums">{formatMoney(revenueMonth)}</p>
        </div>
      </div>
      {/* Plan bar */}
      <div className="mt-3">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-[var(--tg-theme-hint-color)]">План</span>
          <span className="text-sm font-bold tabular-nums">{planPercentage.toFixed(0)}%</span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--tg-theme-bg-color)]">
          <div
            className="h-full rounded-full bg-[var(--tg-theme-button-color)] transition-all duration-700"
            style={{ width: `${Math.min(planPercentage, 100)}%` }}
          />
        </div>
        <p className="mt-1 text-xs tabular-nums text-[var(--tg-theme-hint-color)]">
          {formatMoney(revenueMonth)} из {formatMoney(planTarget)}
        </p>
      </div>
      {/* In shift */}
      <div className="mt-3 flex items-center gap-1 text-sm">
        <span className="text-[var(--tg-theme-hint-color)]">В смене:</span>
        <span className="font-medium">
          {barbersInShift}/{barbersTotal}
        </span>
        <span className="text-[var(--tg-theme-hint-color)]">мастеров</span>
      </div>
    </div>
  )
}

// --- Bingo table: barbers ranked by cumulative revenue ---
function BingoTable({
  barbers,
  thresholdMax,
}: {
  barbers: BarberPVRResponse[]
  thresholdMax: number
}) {
  const sorted = [...barbers].sort(
    (a, b) => b.cumulative_revenue - a.cumulative_revenue,
  )

  return (
    <div className="mx-4 mt-4">
      <h3 className="font-medium">Бинго</h3>
      <div className="mt-2 space-y-2">
        {sorted.map((b, i) => {
          const pct =
            thresholdMax > 0
              ? Math.min((b.cumulative_revenue / thresholdMax) * 100, 100)
              : 0

          return (
            <div
              key={b.barber_id}
              className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-3"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-5 text-center text-sm font-bold text-[var(--tg-theme-hint-color)]">
                    {i + 1}
                  </span>
                  <span className="font-medium">{b.name}</span>
                </div>
                <span className="font-bold tabular-nums">
                  {formatMoney(b.cumulative_revenue)}
                </span>
              </div>
              {/* PVR mini progress */}
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--tg-theme-bg-color)]">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="mt-1 flex items-center justify-between text-xs text-[var(--tg-theme-hint-color)]">
                <span>
                  Премия: {formatMoney(b.bonus_amount)}
                </span>
                {b.next_threshold && b.remaining_to_next !== null && (
                  <span>
                    До след: {formatMoney(b.remaining_to_next)}
                  </span>
                )}
              </div>
            </div>
          )
        })}
        {sorted.length === 0 && (
          <p className="py-4 text-center text-sm text-[var(--tg-theme-hint-color)]">
            Нет данных
          </p>
        )}
      </div>
    </div>
  )
}

// --- Review card ---
function ReviewCard({
  review,
  onProcess,
}: {
  review: ReviewResponse
  onProcess: (review: ReviewResponse) => void
}) {
  const stars = Array.from({ length: 5 }, (_, i) => i < review.rating)
  const createdAt = new Date(review.created_at)
  const timeStr = createdAt.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })
  const dateStr = createdAt.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
  })

  return (
    <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-3">
      <div className="flex items-start justify-between">
        <div>
          <span className="text-base">
            {stars.map((filled, i) => (
              <span key={i} className={filled ? '' : 'opacity-20'}>
                {'\u{2B50}'}
              </span>
            ))}
          </span>
          <p className="mt-1 text-sm font-medium">{review.barber_name}</p>
        </div>
        <span className="text-xs text-[var(--tg-theme-hint-color)]">
          {dateStr}, {timeStr}
        </span>
      </div>
      {review.client_name && (
        <p className="mt-1 text-xs text-[var(--tg-theme-hint-color)]">
          {review.client_name}
        </p>
      )}
      {review.comment && (
        <p className="mt-2 text-sm">{review.comment}</p>
      )}

      {/* Status / action */}
      <div className="mt-3 flex items-center justify-between">
        {review.status === 'processed' ? (
          <span className="text-xs text-emerald-500">
            {'\u{2705}'} Обработан
          </span>
        ) : review.status === 'in_progress' ? (
          <span className="text-xs text-amber-500">
            {'\u{1F504}'} В работе
          </span>
        ) : (
          <span className="text-xs text-red-500">Новый</span>
        )}
        {review.status !== 'processed' && (
          <button
            type="button"
            className="rounded-lg bg-[var(--tg-theme-button-color)] px-3 py-1.5 text-xs font-medium text-[var(--tg-theme-button-text-color)]"
            onClick={() => onProcess(review)}
          >
            Обработать
          </button>
        )}
      </div>

      {/* Processed info */}
      {review.processed_comment && (
        <div className="mt-2 rounded-lg bg-[var(--tg-theme-bg-color)] p-2">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">
            {review.processed_comment}
          </p>
        </div>
      )}
    </div>
  )
}

// --- Reviews feed with filter tabs ---
type FilterTab = 'all' | 'negative' | 'unprocessed'

function ReviewsFeed({
  reviews,
  total,
  activeTab,
  onTabChange,
  onProcess,
  unprocessedCount,
}: {
  reviews: ReviewResponse[]
  total: number
  activeTab: FilterTab
  onTabChange: (tab: FilterTab) => void
  onProcess: (review: ReviewResponse) => void
  unprocessedCount: number
}) {
  const tabs: { key: FilterTab; label: string; badge?: number }[] = [
    { key: 'all', label: 'Все' },
    { key: 'negative', label: 'Негативные' },
    { key: 'unprocessed', label: 'Необработанные', badge: unprocessedCount },
  ]

  return (
    <div className="mx-4 mt-4">
      <h3 className="font-medium">Отзывы</h3>

      {/* Filter tabs */}
      <div className="mt-2 flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`relative rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === t.key
                ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                : 'bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)]'
            }`}
            onClick={() => onTabChange(t.key)}
          >
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                {t.badge}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Reviews list */}
      <div className="mt-3 space-y-2">
        {reviews.map((r) => (
          <ReviewCard key={r.id} review={r} onProcess={onProcess} />
        ))}
        {reviews.length === 0 && (
          <p className="py-4 text-center text-sm text-[var(--tg-theme-hint-color)]">
            Отзывов нет
          </p>
        )}
        {reviews.length > 0 && reviews.length < total && (
          <p className="py-2 text-center text-xs text-[var(--tg-theme-hint-color)]">
            Показано {reviews.length} из {total}
          </p>
        )}
      </div>
    </div>
  )
}

// --- Main BranchScreen ---
export default function BranchScreen() {
  const user = useAuthStore((s) => s.user)
  const branchId = user?.branch_id

  // Kombat store for today stats
  const { todayRating, fetchTodayRating } = useKombatStore()

  // PVR store for Bingo table
  const { branchPvr, thresholds, fetchBranchPvr, fetchThresholds } = usePvrStore()

  // Reviews store
  const {
    reviews,
    total,
    filters,
    isLoading: reviewsLoading,
    fetchReviews,
    setFilters,
    processReview,
    addReview,
  } = useReviewsStore()

  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [processingReview, setProcessingReview] = useState<ReviewResponse | null>(null)
  const [unprocessedCount, setUnprocessedCount] = useState(0)

  // Load data on mount
  useEffect(() => {
    if (branchId) {
      fetchTodayRating(branchId)
      fetchBranchPvr(branchId)
      fetchThresholds()
    }
  }, [branchId, fetchTodayRating, fetchBranchPvr, fetchThresholds])

  // Load reviews when branch or filters change
  useEffect(() => {
    if (branchId) {
      fetchReviews(branchId)
    }
  }, [branchId, filters, fetchReviews])

  // Count unprocessed for badge
  useEffect(() => {
    const count = reviews.filter(
      (r) => r.status === 'new' || r.status === 'in_progress',
    ).length
    setUnprocessedCount(count)
  }, [reviews])

  // Handle filter tab changes
  const handleTabChange = useCallback(
    (tab: FilterTab) => {
      setActiveTab(tab)
      switch (tab) {
        case 'all':
          setFilters({})
          break
        case 'negative':
          setFilters({ ratingMax: 3 })
          break
        case 'unprocessed':
          setFilters({ status: 'new' as ReviewStatus })
          break
      }
    },
    [setFilters],
  )

  // WebSocket for real-time reviews
  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      if (message.type === 'new_review') {
        const data = message.data as { branch_id?: string; review?: ReviewResponse }
        if (data.branch_id === branchId && data.review) {
          addReview(data.review)
        }
      }
    },
    [branchId, addReview],
  )
  useWebSocket(handleWSMessage)

  // Derived stats from todayRating
  const revenueToday = todayRating
    ? todayRating.ratings.reduce((sum, r) => sum + r.revenue, 0)
    : 0
  const revenueMonth = todayRating?.plan?.current ?? 0
  const planPercentage = todayRating?.plan?.percentage ?? 0
  const planTarget = todayRating?.plan?.target ?? 0
  const barbersInShift = todayRating?.ratings.length ?? 0
  const barbersTotal = branchPvr?.barbers.length ?? barbersInShift

  // Max threshold for progress bar scaling
  const thresholdMax =
    thresholds.length > 0
      ? Math.max(...thresholds.map((t) => t.amount))
      : 0

  if (!branchId) {
    return (
      <div className="p-8 text-center text-[var(--tg-theme-hint-color)]">
        Филиал не назначен
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      {/* Header */}
      <h1 className="px-4 text-lg font-bold">
        {todayRating?.branch_name ?? 'Филиал'}
      </h1>

      {/* Today stats */}
      <div className="mt-3">
        {todayRating ? (
          <TodayStats
            revenueToday={revenueToday}
            revenueMonth={revenueMonth}
            planPercentage={planPercentage}
            planTarget={planTarget}
            barbersInShift={barbersInShift}
            barbersTotal={barbersTotal}
          />
        ) : (
          <div className="mx-4">
            <LoadingSkeleton lines={4} />
          </div>
        )}
      </div>

      {/* Bingo table */}
      {branchPvr ? (
        <BingoTable barbers={branchPvr.barbers} thresholdMax={thresholdMax} />
      ) : (
        <div className="mx-4 mt-4">
          <LoadingSkeleton lines={3} />
        </div>
      )}

      {/* Reviews feed */}
      {reviewsLoading && reviews.length === 0 ? (
        <div className="mx-4 mt-4">
          <LoadingSkeleton lines={4} />
        </div>
      ) : (
        <ReviewsFeed
          reviews={reviews}
          total={total}
          activeTab={activeTab}
          onTabChange={handleTabChange}
          onProcess={setProcessingReview}
          unprocessedCount={unprocessedCount}
        />
      )}

      {/* Process review modal */}
      {processingReview && (
        <ReviewProcessModal
          review={processingReview}
          onClose={() => setProcessingReview(null)}
          onSubmit={processReview}
        />
      )}
    </div>
  )
}
