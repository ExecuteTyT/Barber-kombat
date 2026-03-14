import { useEffect, useState, useCallback, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

import {
  StarRating,
  IconCheckCircle,
  IconRefresh,
  IconArrowLeft,
  IconShoppingBag,
  IconGift,
  IconTarget,
  IconCrown,
  IconStar,
} from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useAuthStore } from '../../stores/authStore'
import { useKombatStore } from '../../stores/kombatStore'
import { usePvrStore } from '../../stores/pvrStore'
import { useReviewsStore } from '../../stores/reviewsStore'
import { useChefAnalyticsStore } from '../../stores/chefAnalyticsStore'
import ReviewProcessModal from './ReviewProcessModal'
import type {
  BarberPVRResponse,
  BranchAnalytics,
  RatingEntry,
  ReviewResponse,
  ReviewStatus,
  WSMessage,
} from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

// --- Analytics KPI cards ---

function KPIGrid({ analytics }: { analytics: BranchAnalytics }) {
  const kpis = [
    {
      label: 'Выручка сегодня',
      value: formatMoney(analytics.revenue_today),
      accent: true,
    },
    {
      label: 'С начала месяца',
      value: formatMoney(analytics.revenue_mtd),
    },
    {
      label: 'Средний чек',
      value: formatMoney(analytics.avg_check_today),
      sub: `За месяц: ${formatMoney(analytics.avg_check_mtd)}`,
    },
    {
      label: 'Визитов сегодня',
      value: String(analytics.visits_today),
      sub: `За месяц: ${analytics.visits_mtd}`,
    },
    {
      label: 'Клиентов сегодня',
      value: String(analytics.clients_today),
      sub: `Новых: ${analytics.new_clients_mtd} / Повторных: ${analytics.returning_clients_mtd}`,
    },
    {
      label: 'В смене',
      value: `${analytics.barbers_in_shift} / ${analytics.barbers_total}`,
    },
  ]

  return (
    <div className="mx-4 grid grid-cols-2 gap-2">
      {kpis.map((k) => (
        <div key={k.label} className="bk-card p-3">
          <p className="text-[10px] uppercase tracking-wider text-[var(--bk-text-dim)]">
            {k.label}
          </p>
          <p
            className={`mt-0.5 text-lg font-bold tabular-nums ${k.accent ? 'text-[var(--bk-gold)]' : 'text-[var(--bk-text)]'}`}
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {k.value}
          </p>
          {k.sub && (
            <p className="mt-0.5 text-[10px] text-[var(--bk-text-dim)]">{k.sub}</p>
          )}
        </div>
      ))}
    </div>
  )
}

// --- Plan progress ---

function PlanProgress({ analytics }: { analytics: BranchAnalytics }) {
  if (analytics.plan_target <= 0) return null

  return (
    <div className="mx-4 mt-3">
      <div className="bk-card p-3">
        <div className="flex items-center gap-1.5">
          <IconTarget size={14} className="text-[var(--bk-gold)]" />
          <span className="text-xs font-semibold text-[var(--bk-text)]">План месяца</span>
        </div>
        <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
          <div
            className="bk-progress-fill h-full transition-all duration-700"
            style={{ width: `${Math.min(analytics.plan_percentage, 100)}%` }}
          />
        </div>
        <div className="mt-1.5 flex items-baseline justify-between">
          <span className="text-xs tabular-nums text-[var(--bk-text-dim)]">
            {formatMoney(analytics.revenue_mtd)} из {formatMoney(analytics.plan_target)}
          </span>
          <span className="text-sm font-bold tabular-nums text-[var(--bk-gold)]">
            {analytics.plan_percentage.toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  )
}

// --- Monthly metrics row ---

function MonthlyMetrics({ analytics }: { analytics: BranchAnalytics }) {
  return (
    <div className="mx-4 mt-3 flex gap-2">
      <div className="bk-card flex flex-1 items-center gap-2 p-3">
        <IconShoppingBag size={16} className="text-[var(--bk-text-secondary)]" />
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[var(--bk-text-dim)]">
            Товары
          </p>
          <p className="text-base font-bold tabular-nums text-[var(--bk-text)]">
            {analytics.total_products_mtd}
          </p>
        </div>
      </div>
      <div className="bk-card flex flex-1 items-center gap-2 p-3">
        <IconGift size={16} className="text-[var(--bk-text-secondary)]" />
        <div>
          <p className="text-[10px] uppercase tracking-wider text-[var(--bk-text-dim)]">
            Доп. услуги
          </p>
          <p className="text-base font-bold tabular-nums text-[var(--bk-text)]">
            {analytics.total_extras_mtd}
          </p>
        </div>
      </div>
      {analytics.avg_review_score !== null && (
        <div className="bk-card flex flex-1 items-center gap-2 p-3">
          <IconStar size={16} className="text-[var(--bk-gold)]" />
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--bk-text-dim)]">
              Отзывы
            </p>
            <p className="text-base font-bold tabular-nums text-[var(--bk-text)]">
              {analytics.avg_review_score.toFixed(1)}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

// --- Today rating table ---

function TodayRatingTable({ ratings }: { ratings: RatingEntry[] }) {
  if (ratings.length === 0) return null

  return (
    <div className="mx-4 mt-4">
      <h3 className="bk-heading text-base">Барберы сегодня</h3>
      <div className="mt-2 space-y-1.5">
        {ratings.map((r) => {
          const medalColors: Record<number, string> = {
            1: 'text-[var(--bk-gold)]',
            2: 'text-[#C0C0C0]',
            3: 'text-[#CD7F32]',
          }
          const medal = medalColors[r.rank]

          return (
            <div key={r.barber_id} className="bk-card p-3">
              <div className="flex items-center gap-3">
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    medal
                      ? `${medal} bg-[var(--bk-bg-elevated)]`
                      : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-dim)]'
                  }`}
                >
                  {r.rank <= 3 ? <IconCrown size={14} /> : r.rank}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--bk-text)] truncate">{r.name}</p>
                </div>
                <span
                  className="text-base font-bold tabular-nums text-[var(--bk-text)]"
                  style={{ fontFamily: 'var(--bk-font-heading)' }}
                >
                  {formatMoney(r.revenue)}
                </span>
              </div>
              <div className="mt-1.5 ml-10 flex gap-3 text-[10px] text-[var(--bk-text-dim)]">
                <span>Рейтинг: {r.total_score.toFixed(0)}</span>
                <span>Ср. чек ×{r.cs_value.toFixed(2)}</span>
                <span>Товары {r.products_count}</span>
                <span>Доп. услуги {r.extras_count}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// --- Premium bonuses ---

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
      <h3 className="bk-heading text-base">Премии за выручку</h3>
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
                  <span>До следующего порога: {formatMoney(b.remaining_to_next)}</span>
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

// --- Reviews ---

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

// --- Main screen ---

export default function BranchScreen() {
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const { branchId: urlBranchId } = useParams<{ branchId: string }>()
  // Owner navigates via /owner/branch/:branchId (URL param),
  // Chef has branch_id on their user profile
  const branchId = urlBranchId ?? user?.branch_id
  const showBackButton = !!urlBranchId

  const { todayRating, fetchTodayRating } = useKombatStore()
  const { branchPvr, thresholds, fetchBranchPvr, fetchThresholds } = usePvrStore()
  const { analytics, fetchAnalytics } = useChefAnalyticsStore()
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
      fetchAnalytics(branchId)
    }
  }, [branchId, fetchTodayRating, fetchBranchPvr, fetchThresholds, fetchAnalytics])

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

  const thresholdMax = thresholds.length > 0 ? Math.max(...thresholds.map((t) => t.amount)) : 0

  if (!branchId) {
    return <div className="p-8 text-center text-[var(--bk-text-secondary)]">Филиал не назначен</div>
  }

  const branchName = analytics?.branch_name ?? todayRating?.branch_name ?? 'Филиал'

  return (
    <div className="pb-4 pt-4">
      {/* Header */}
      <div className="flex items-center gap-2 px-4">
        {showBackButton && (
          <button
            type="button"
            className="flex items-center gap-1 text-sm text-[var(--bk-gold)]"
            onClick={() => navigate(-1)}
          >
            <IconArrowLeft size={18} />
          </button>
        )}
        <h1 className="bk-heading text-xl">{branchName}</h1>
      </div>

      {/* Analytics KPIs */}
      <div className="mt-3">
        {analytics ? (
          <>
            <KPIGrid analytics={analytics} />
            <PlanProgress analytics={analytics} />
            <MonthlyMetrics analytics={analytics} />
          </>
        ) : (
          <div className="mx-4">
            <LoadingSkeleton lines={6} />
          </div>
        )}
      </div>

      {/* Today rating */}
      {todayRating && <TodayRatingTable ratings={todayRating.ratings} />}

      {/* PVR Bingo */}
      {branchPvr ? (
        <BingoTable barbers={branchPvr.barbers} thresholdMax={thresholdMax} />
      ) : (
        <div className="mx-4 mt-4">
          <LoadingSkeleton lines={3} />
        </div>
      )}

      {/* Reviews */}
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
