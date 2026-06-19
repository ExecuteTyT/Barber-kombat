import Button from './Button'
import { IconAlertCircle, IconCheckCircle, IconRefresh, StarRating } from './Icons'
import type { ReviewResponse } from '../types'

/** A single review with status and a "process" action. Shared by owner and admin. */
export default function ReviewCard({
  review,
  onProcess,
}: {
  review: ReviewResponse
  onProcess: (review: ReviewResponse) => void
}) {
  const createdAt = new Date(review.created_at)
  const timeStr = createdAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  const dateStr = createdAt.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })

  // The whole card opens the process modal for new / in-progress reviews.
  const clickable = review.status !== 'processed'

  return (
    <div
      className={`bk-card p-3${clickable ? ' cursor-pointer' : ''}`}
      onClick={clickable ? () => onProcess(review) : undefined}
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onProcess(review)
              }
            }
          : undefined
      }
    >
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
          <span className="flex items-center gap-1 text-xs font-medium text-[var(--bk-red)]">
            <IconAlertCircle size={14} /> Новый
          </span>
        )}
        {review.status !== 'processed' && (
          <Button
            onClick={(e) => {
              e.stopPropagation()
              onProcess(review)
            }}
          >
            Обработать
          </Button>
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
