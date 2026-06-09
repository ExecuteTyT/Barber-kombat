import { useEffect, useRef, useState } from 'react'

import { IconCopy, IconMessageCircle, IconPhone, StarRating } from './Icons'
import { phoneDigits, telLink, waLink } from '../lib/contact'
import { useToastStore } from '../stores/toastStore'
import type { ReviewResponse } from '../types'

interface ReviewProcessModalProps {
  review: ReviewResponse
  onClose: () => void
  onSubmit: (
    reviewId: string,
    status: 'in_progress' | 'processed',
    comment: string,
  ) => Promise<boolean>
}

const COMMENT_MAX = 2000

/** Quick-reply templates that pre-fill the WhatsApp message to the client. */
const TEMPLATES: { label: string; text: string }[] = [
  {
    label: 'Извинение',
    text: 'Здравствуйте! Очень жаль, что визит вас разочаровал. Подскажите, что пошло не так — мы хотим всё исправить.',
  },
  {
    label: 'Приглашение',
    text: 'Здравствуйте! Будем рады видеть вас снова — подберём удобное время и лучшего мастера.',
  },
  {
    label: 'Компенсация',
    text: 'Здравствуйте! Приносим извинения за неудобства. В качестве компенсации предлагаем скидку на следующий визит.',
  },
]

export default function ReviewProcessModal({ review, onClose, onSubmit }: ReviewProcessModalProps) {
  // Pre-fill with the existing resolution note so re-opening an in-progress
  // review keeps what was written instead of wiping it.
  const [comment, setComment] = useState(review.processed_comment ?? '')
  const [message, setMessage] = useState('')
  const [status, setStatus] = useState<'in_progress' | 'processed'>(
    review.status === 'new' ? 'in_progress' : 'processed',
  )
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const showToast = useToastStore((s) => s.show)

  const hasPhone = phoneDigits(review.client_phone) !== ''

  // Escape to close, Tab trapped within the sheet, body scroll locked.
  useEffect(() => {
    const el = containerRef.current
    const focusables = () =>
      Array.from(
        el?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), textarea, input, [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      )
    focusables()[0]?.focus()

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key === 'Tab') {
        const items = focusables()
        if (items.length === 0) return
        const first = items[0]
        const last = items[items.length - 1]
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault()
          last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
    }
  }, [onClose])

  const handleSubmit = async () => {
    if (!comment.trim()) {
      setError('Введите комментарий')
      return
    }
    setIsSubmitting(true)
    setError(null)
    const success = await onSubmit(review.id, status, comment.trim())
    if (success) {
      showToast('Отзыв обработан', 'success')
      onClose()
    } else {
      setError('Не удалось обработать отзыв')
      setIsSubmitting(false)
    }
  }

  const copyPhone = async () => {
    if (!review.client_phone) return
    const text = review.client_phone
    try {
      if (!navigator.clipboard?.writeText) throw new Error('no clipboard api')
      await navigator.clipboard.writeText(text)
      showToast('Телефон скопирован', 'success')
      return
    } catch {
      // Fallback for non-secure contexts / older browsers
      try {
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.focus()
        ta.select()
        const ok = document.execCommand('copy')
        document.body.removeChild(ta)
        showToast(ok ? 'Телефон скопирован' : 'Не удалось скопировать', ok ? 'success' : 'error')
      } catch {
        showToast('Не удалось скопировать', 'error')
      }
    }
  }

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center"
      role="dialog"
      aria-modal="true"
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div
        ref={containerRef}
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

        {/* Client outreach */}
        {hasPhone && (
          <div className="mt-4 rounded-xl border border-[var(--bk-border)] p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-[var(--bk-text)]">
                Связаться с клиентом
              </span>
              <span className="text-xs text-[var(--bk-text-dim)]">{review.client_phone}</span>
            </div>

            <div className="mt-2 flex flex-wrap gap-1.5">
              {TEMPLATES.map((t) => (
                <button
                  key={t.label}
                  type="button"
                  className="rounded-full bg-[var(--bk-bg-elevated)] px-3 py-1.5 text-xs font-medium text-[var(--bk-text-secondary)]"
                  onClick={() => setMessage(t.text)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <textarea
              className="mt-2 w-full rounded-xl border border-[var(--bk-border)] bg-[var(--bk-bg-input)] p-3 text-sm text-[var(--bk-text)] placeholder-[var(--bk-text-dim)]"
              rows={2}
              placeholder="Сообщение клиенту (откроется в WhatsApp)..."
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />

            <div className="mt-2 flex gap-2">
              <a
                href={waLink(review.client_phone, message) ?? undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl bg-[var(--bk-green)] text-sm font-semibold text-white"
              >
                <IconMessageCircle size={16} /> WhatsApp
              </a>
              <a
                href={telLink(review.client_phone) ?? undefined}
                className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl bg-[var(--bk-bg-elevated)] text-sm font-semibold text-[var(--bk-text)]"
              >
                <IconPhone size={16} /> Позвонить
              </a>
              <button
                type="button"
                onClick={copyPhone}
                aria-label="Скопировать телефон"
                className="flex min-h-[44px] w-12 items-center justify-center rounded-xl bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]"
              >
                <IconCopy size={16} />
              </button>
            </div>
          </div>
        )}

        {/* Resolution (internal) */}
        <div className="mt-4">
          <label className="text-sm font-medium text-[var(--bk-text)]">Статус</label>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className={`min-h-[44px] flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
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
              className={`min-h-[44px] flex-1 rounded-lg px-3 py-2.5 text-sm font-semibold transition-colors ${
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
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-[var(--bk-text)]">Что было сделано</label>
            <span className="text-xs text-[var(--bk-text-dim)]">
              {comment.length}/{COMMENT_MAX}
            </span>
          </div>
          <textarea
            className="mt-2 w-full rounded-xl border border-[var(--bk-border)] bg-[var(--bk-bg-input)] p-3 text-sm text-[var(--bk-text)] placeholder-[var(--bk-text-dim)]"
            rows={3}
            placeholder="Внутренняя заметка: как разрешили ситуацию..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={COMMENT_MAX}
          />
        </div>

        {error && <p className="mt-2 text-sm text-[var(--bk-red)]">{error}</p>}

        <div className="mt-4 flex gap-3">
          <button
            type="button"
            className="min-h-[44px] flex-1 rounded-xl bg-[var(--bk-bg-elevated)] py-3 text-sm font-semibold text-[var(--bk-text-secondary)]"
            onClick={onClose}
          >
            Отмена
          </button>
          <button
            type="button"
            className="min-h-[44px] flex-1 rounded-xl bg-[var(--bk-gold)] py-3 text-sm font-semibold text-[var(--bk-bg-primary)] disabled:opacity-50"
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
