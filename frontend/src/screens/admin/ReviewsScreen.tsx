import { useCallback, useEffect, useMemo, useState } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import ReviewProcessModal from '../../components/ReviewProcessModal'
import ReviewsList, { type ReviewFilterTab } from '../../components/ReviewsList'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useAuthStore } from '../../stores/authStore'
import { useReviewsStore } from '../../stores/reviewsStore'
import type { ReviewResponse, ReviewStatus, WSMessage } from '../../types'

/** Admin reviews workspace — scoped to the admin's own branch. */
export default function ReviewsScreen() {
  const user = useAuthStore((s) => s.user)
  const branchId = user?.branch_id ?? undefined
  const {
    reviews,
    total,
    filters,
    isLoading,
    isLoadingMore,
    error,
    fetchReviews,
    loadMore,
    setFilters,
    processReview,
    addReview,
  } = useReviewsStore()

  const [activeTab, setActiveTab] = useState<ReviewFilterTab>('unprocessed')
  const [processing, setProcessing] = useState<ReviewResponse | null>(null)
  const unprocessedCount = useMemo(
    () => reviews.filter((r) => r.status === 'new' || r.status === 'in_progress').length,
    [reviews],
  )

  // Admins land on unprocessed reviews for their branch.
  useEffect(() => {
    setFilters({ status: 'new' as ReviewStatus })
  }, [setFilters])

  useEffect(() => {
    if (branchId) fetchReviews(branchId)
  }, [branchId, filters, fetchReviews])

  const handleTabChange = useCallback(
    (tab: ReviewFilterTab) => {
      setActiveTab(tab)
      if (tab === 'all') setFilters({})
      else if (tab === 'negative') setFilters({ ratingMax: 3 })
      else setFilters({ status: 'new' as ReviewStatus })
    },
    [setFilters],
  )

  const handleWS = useCallback(
    (m: WSMessage) => {
      if (m.type === 'new_review') {
        const data = m.data as { branch_id?: string; review?: ReviewResponse }
        if (data.branch_id === branchId && data.review) addReview(data.review)
      }
    },
    [branchId, addReview],
  )
  useWebSocket(handleWS)

  if (!branchId) {
    return <div className="p-8 text-center text-[var(--bk-text-secondary)]">Филиал не назначен</div>
  }

  return (
    <div className="px-4 pb-4 pt-4">
      <h1 className="bk-heading text-xl">Отзывы</h1>
      <p className="mt-0.5 text-xs text-[var(--bk-text-secondary)]">
        Обработка отзывов вашего филиала
      </p>

      <div className="mt-4">
        {isLoading && reviews.length === 0 ? (
          <LoadingSkeleton lines={5} />
        ) : error ? (
          <p className="py-8 text-center text-sm text-[var(--bk-red)]">{error}</p>
        ) : (
          <ReviewsList
            reviews={reviews}
            total={total}
            activeTab={activeTab}
            onTabChange={handleTabChange}
            onProcess={setProcessing}
            unprocessedCount={unprocessedCount}
            onLoadMore={() => loadMore(branchId)}
            isLoadingMore={isLoadingMore}
          />
        )}
      </div>

      {processing && (
        <ReviewProcessModal
          review={processing}
          onClose={() => setProcessing(null)}
          onSubmit={processReview}
        />
      )}
    </div>
  )
}
