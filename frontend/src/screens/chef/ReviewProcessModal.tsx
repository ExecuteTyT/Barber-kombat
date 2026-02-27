import { useState } from 'react'

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
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Modal */}
      <div
        className="relative w-full max-w-lg rounded-t-2xl bg-[var(--tg-theme-bg-color)] px-4 pb-8 pt-4"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 2rem)' }}
      >
        {/* Handle */}
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-[var(--tg-theme-hint-color)]/30" />

        <h3 className="text-lg font-bold">Обработка отзыва</h3>

        {/* Review preview */}
        <div className="mt-3 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">
              {Array.from({ length: 5 }, (_, i) => (
                <span key={i} className={i < review.rating ? '' : 'opacity-20'}>
                  {'\u{2B50}'}
                </span>
              ))}
            </span>
          </div>
          <p className="mt-1 text-sm text-[var(--tg-theme-hint-color)]">
            {review.barber_name}
            {review.client_name && ` \u{2022} ${review.client_name}`}
          </p>
          {review.comment && <p className="mt-2 text-sm">{review.comment}</p>}
        </div>

        {/* Status selector */}
        <div className="mt-4">
          <label className="text-sm font-medium">Статус</label>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                status === 'in_progress'
                  ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                  : 'bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)]'
              }`}
              onClick={() => setStatus('in_progress')}
            >
              В работе
            </button>
            <button
              type="button"
              className={`flex-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                status === 'processed'
                  ? 'bg-[var(--tg-theme-button-color)] text-[var(--tg-theme-button-text-color)]'
                  : 'bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)]'
              }`}
              onClick={() => setStatus('processed')}
            >
              Обработан
            </button>
          </div>
        </div>

        {/* Comment */}
        <div className="mt-4">
          <label className="text-sm font-medium">Комментарий</label>
          <textarea
            className="mt-2 w-full rounded-xl border border-[var(--tg-theme-hint-color)]/20 bg-[var(--tg-theme-secondary-bg-color)] p-3 text-sm text-[var(--tg-theme-text-color)] placeholder-[var(--tg-theme-hint-color)] focus:border-[var(--tg-theme-button-color)] focus:outline-none"
            rows={3}
            placeholder="Что было сделано..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
          />
        </div>

        {error && (
          <p className="mt-2 text-sm text-[var(--tg-theme-destructive-text-color)]">{error}</p>
        )}

        {/* Actions */}
        <div className="mt-4 flex gap-3">
          <button
            type="button"
            className="flex-1 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] py-3 text-sm font-medium"
            onClick={onClose}
          >
            Отмена
          </button>
          <button
            type="button"
            className="flex-1 rounded-xl bg-[var(--tg-theme-button-color)] py-3 text-sm font-medium text-[var(--tg-theme-button-text-color)] disabled:opacity-50"
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
