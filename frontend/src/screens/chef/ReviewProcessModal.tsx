import { useState } from 'react'

import { StarRating } from '../../components/Icons'
import type { ReviewResponse } from '../../types'

interface ReviewProcessModalProps {
  review: ReviewResponse
  onClose: () => void
  onSubmit: (
    reviewId: string,
    status: 'in_progress' | 'processed',
    comment: string,
  ) => Promise<boolean>
}

export default function ReviewProcessModal({ review, onClose, onSubmit }: ReviewProcessModalProps) {
  const [comment, setComment] = useState('')
  const [status, setStatus] = useState<'in_progress' | 'processed'>(
    review.status === 'new' ? 'in_progress' : 'processed',
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    if (!comment.trim()) {
      setError('Введите комментарий')
      return
    }
    setIsSubmitting(true)
    setError(null)

    const success = await onSubmit(review.id, status, comment.trim())
    if (success) {
      onClose()
    } else {
      setError('Не удалось обработать отзыв')
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div
        className="relative w-full max-w-lg overflow-y-auto rounded-t-2xl border-t border-[var(--bk-border-gold)] bg-[var(--bk-bg-primary)] px-4 pb-8 pt-4"
        style={{ maxHeight: '90vh', paddingBottom: 'calc(env(safe-area-inset-bottom) + 2rem)' }}
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[var(--bk-text-dim)]" />

        <h3 className="bk-heading text-xl">Обработка отзыва</h3>

        <div className="bk-card mt-3 p-3">
          <StarRating rating={review.rating} />
          <p className="mt-1 text-sm text-[var(--bk-text-secondary)]">
            {review.barber_name}
            {review.client_name && ` \u{2022} ${review.client_name}`}
          </p>
          {review.comment && <p className="mt-2 text-sm text-[var(--bk-text)]">{review.comment}</p>}
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium text-[var(--bk-text)]">Статус</label>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className={`flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
                status === 'in_progress'
                  ? 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]'
                  : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]'
              }`}
              onClick={() => setStatus('in_progress')}
            >
              В работе
            </button>
            <button
              type="button"
              className={`flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
                status === 'processed'
                  ? 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]'
                  : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]'
              }`}
              onClick={() => setStatus('processed')}
            >
              Обработан
            </button>
          </div>
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium text-[var(--bk-text)]">Комментарий</label>
          <textarea
            className="mt-2 w-full rounded-xl border border-[var(--bk-border)] bg-[var(--bk-bg-input)] p-3 text-sm text-[var(--bk-text)] placeholder-[var(--bk-text-dim)]"
            rows={3}
            placeholder="Что было сделано..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
          />
        </div>

        {error && <p className="mt-2 text-sm text-[var(--bk-red)]">{error}</p>}

        <div className="mt-4 flex gap-3">
          <button
            type="button"
            className="flex-1 rounded-xl bg-[var(--bk-bg-elevated)] py-3 text-sm font-semibold text-[var(--bk-text-secondary)]"
            onClick={onClose}
          >
            Отмена
          </button>
          <button
            type="button"
            className="flex-1 rounded-xl bg-[var(--bk-gold)] py-3 text-sm font-semibold text-[var(--bk-bg-primary)] disabled:opacity-50"
            disabled={isSubmitting || !comment.trim()}
            onClick={handleSubmit}
          >
            {isSubmitting ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </div>
  )
}
