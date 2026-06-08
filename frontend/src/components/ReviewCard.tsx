import { IconCheckCircle, IconRefresh, StarRating } from './Icons'
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
            className="min-h-[44px] rounded-lg bg-[var(--bk-gold)] px-4 py-2 text-sm font-semibold text-[var(--bk-bg-primary)]"
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
