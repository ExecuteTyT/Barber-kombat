import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams } from 'react-router-dom'

import { StarRating, IconCheckCircle, IconRefresh, IconUsers } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useAuthStore } from '../../stores/authStore'
import { useKombatStore } from '../../stores/kombatStore'
import { usePvrStore } from '../../stores/pvrStore'
import { useReviewsStore } from '../../stores/reviewsStore'
import ReviewProcessModal from './ReviewProcessModal'
import type { BarberPVRResponse, ReviewResponse, ReviewStatus, WSMessage } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

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
    <div className="bk-card mx-4 p-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <p className="text-xs text-[var(--bk-text-secondary)]">Выручка дня</p>
          <p
            className="text-lg font-bold tabular-nums"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {formatMoney(revenueToday)}
          </p>
        </div>
        <div>
          <p className="text-xs text-[var(--bk-text-secondary)]">Выручка месяца</p>
          <p
            className="text-lg font-bold tabular-nums"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {formatMoney(revenueMonth)}
          </p>
        </div>
      </div>
      <div className="mt-3">
        <div className="flex items-baseline justify-between">
          <span className="text-xs text-[var(--bk-text-secondary)]">План</span>
          <span className="text-sm font-bold tabular-nums text-[var(--bk-gold)]">
            {planPercentage.toFixed(0)}%
          </span>
        </div>
        <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
          <div
            className="bk-progress-fill h-full transition-all duration-700"
            style={{ width: `${Math.min(planPercentage, 100)}%` }}
          />
        </div>
        <p className="mt-1 text-xs tabular-nums text-[var(--bk-text-dim)]">
          {formatMoney(revenueMonth)} из {formatMoney(planTarget)}
        </p>
      </div>
      <div className="mt-3 flex items-center gap-1.5 text-sm">
        <IconUsers size={14} className="text-[var(--bk-text-secondary)]" />
        <span className="text-[var(--bk-text-secondary)]">В смене:</span>
        <span className="font-medium text-[var(--bk-text)]">
          {barbersInShift}/{barbersTotal}
        </span>
      </div>
    </div>
  )
}

function BingoTable({
  barbers,
  thresholdMax,
}: {
  barbers: BarberPVRResponse[]
  thresholdMax: number
}) {
  const sorted = [...barbers].sort((a, b) => b.cumulative_revenue - a.cumulative_revenue)

  return (
    <div className="mx-4 mt-4">
      <h3 className="bk-heading text-base">Бинго</h3>
      <div className="mt-2 space-y-2">
        {sorted.map((b, i) => {
          const pct =
            thresholdMax > 0 ? Math.min((b.cumulative_revenue / thresholdMax) * 100, 100) : 0

          return (
            <div key={b.barber_id} className="bk-card p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--bk-bg-elevated)] text-xs font-bold text-[var(--bk-text-dim)]">
                    {i + 1}
                  </span>
                  <span className="font-medium text-[var(--bk-text)]">{b.name}</span>
                </div>
                <span className="font-bold tabular-nums text-[var(--bk-text)]">
                  {formatMoney(b.cumulative_revenue)}
                </span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
                <div
                  className="bk-progress-fill h-full transition-all duration-500"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <div className="mt-1 flex items-center justify-between text-xs text-[var(--bk-text-dim)]">
                <span>Премия: {formatMoney(b.bonus_amount)}</span>
                {b.next_threshold && b.remaining_to_next !== null && (
                  <span>До след: {formatMoney(b.remaining_to_next)}</span>
                )}
              </div>
            </div>
          )
        })}
        {sorted.length === 0 && (
          <p className="py-4 text-center text-sm text-[var(--bk-text-secondary)]">Нет данных</p>
        )}
      </div>
    </div>
  )
}

function ReviewCard({
  review,
  onProcess,
}: {
  review: ReviewResponse
  onProcess: (review: ReviewResponse) => void
}) {
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
    <div className="bk-card p-3">
      <div className="flex items-start justify-between">
        <div>
          <StarRating rating={review.rating} />
          <p className="mt-1 text-sm font-medium text-[var(--bk-text)]">{review.barber_name}</p>
        </div>
        <span className="text-xs text-[var(--bk-text-dim)]">
          {dateStr}, {timeStr}
        </span>
      </div>
      {review.client_name && (
        <p className="mt-1 text-xs text-[var(--bk-text-secondary)]">{review.client_name}</p>
      )}
      {review.comment && <p className="mt-2 text-sm text-[var(--bk-text)]">{review.comment}</p>}

      <div className="mt-3 flex items-center justify-between">
        {review.status === 'processed' ? (
          <span className="flex items-center gap-1 text-xs text-[var(--bk-green)]">
            <IconCheckCircle size={14} /> Обработан
          </span>
        ) : review.status === 'in_progress' ? (
          <span className="flex items-center gap-1 text-xs text-[var(--bk-gold)]">
            <IconRefresh size={14} /> В работе
          </span>
        ) : (
          <span className="text-xs font-medium text-[var(--bk-red)]">Новый</span>
        )}
        {review.status !== 'processed' && (
          <button
            type="button"
            className="rounded-lg bg-[var(--bk-gold)] px-3 py-1.5 text-xs font-semibold text-[var(--bk-bg-primary)]"
            onClick={() => onProcess(review)}
          >
            Обработать
          </button>
        )}
      </div>

      {review.processed_comment && (
        <div className="mt-2 rounded-lg bg-[var(--bk-bg-elevated)] p-2">
          <p className="text-xs text-[var(--bk-text-secondary)]">{review.processed_comment}</p>
        </div>
      )}
    </div>
  )
}

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
      <h3 className="bk-heading text-base">Отзывы</h3>

      <div className="mt-2 flex gap-2">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`relative rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              activeTab === t.key
                ? 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]'
                : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]'
            }`}
            onClick={() => onTabChange(t.key)}
          >
            {t.label}
            {t.badge !== undefined && t.badge > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--bk-red)] px-1 text-[10px] font-bold text-white">
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
          <p className="py-4 text-center text-sm text-[var(--bk-text-secondary)]">Отзывов нет</p>
        )}
        {reviews.length > 0 && reviews.length < total && (
          <p className="py-2 text-center text-xs text-[var(--bk-text-dim)]">
            Показано {reviews.length} из {total}
          </p>
        )}
      </div>
    </div>
  )
}

export default function BranchScreen() {
  const user = useAuthStore((s) => s.user)
  const { branchId: urlBranchId } = useParams<{ branchId: string }>()
  // Owner navigates via /owner/branch/:branchId (URL param),
  // Chef has branch_id on their user profile
  const branchId = urlBranchId ?? user?.branch_id

  const { todayRating, fetchTodayRating } = useKombatStore()
  const { branchPvr, thresholds, fetchBranchPvr, fetchThresholds } = usePvrStore()
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
  const unprocessedCount = useMemo(
    () => reviews.filter((r) => r.status === 'new' || r.status === 'in_progress').length,
    [reviews],
  )

  useEffect(() => {
    if (branchId) {
      fetchTodayRating(branchId)
      fetchBranchPvr(branchId)
      fetchThresholds()
    }
  }, [branchId, fetchTodayRating, fetchBranchPvr, fetchThresholds])

  useEffect(() => {
    if (branchId) {
      fetchReviews(branchId)
    }
  }, [branchId, filters, fetchReviews])

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

  const revenueToday = todayRating ? todayRating.ratings.reduce((sum, r) => sum + r.revenue, 0) : 0
  const revenueMonth = todayRating?.plan?.current ?? 0
  const planPercentage = todayRating?.plan?.percentage ?? 0
  const planTarget = todayRating?.plan?.target ?? 0
  const barbersInShift = todayRating?.ratings.length ?? 0
  const barbersTotal = branchPvr?.barbers.length ?? barbersInShift

  const thresholdMax = thresholds.length > 0 ? Math.max(...thresholds.map((t) => t.amount)) : 0

  if (!branchId) {
    return <div className="p-8 text-center text-[var(--bk-text-secondary)]">Филиал не назначен</div>
  }

  return (
    <div className="pb-4 pt-4">
      <h1 className="bk-heading px-4 text-xl">{todayRating?.branch_name ?? 'Филиал'}</h1>

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

      {branchPvr ? (
        <BingoTable barbers={branchPvr.barbers} thresholdMax={thresholdMax} />
      ) : (
        <div className="mx-4 mt-4">
          <LoadingSkeleton lines={3} />
        </div>
      )}

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
