import { useState, useEffect, useCallback } from 'react'

const API_BASE = `${import.meta.env.VITE_API_URL ?? ''}/api/v1`

type Phase = 'loading' | 'form' | 'success' | 'error'

interface ReviewInfo {
  barber_name: string
  branch_name: string
  branch_address: string
}

function GoldStar({
  filled,
  hovered,
  index,
  onSelect,
  onHover,
  onLeave,
}: {
  filled: boolean
  hovered: boolean
  index: number
  onSelect: () => void
  onHover: () => void
  onLeave: () => void
}) {
  const active = filled || hovered
  return (
    <button
      type="button"
      className="review-star"
      style={{
        animationDelay: `${index * 60}ms`,
        transform: active ? 'scale(1.15)' : 'scale(1)',
        filter: active
          ? 'drop-shadow(0 0 12px rgba(201, 168, 76, 0.5))'
          : 'none',
        transition: 'transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.3s ease',
      }}
      onClick={onSelect}
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      aria-label={`${index + 1} star`}
    >
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
        <defs>
          <linearGradient id={`star-grad-${index}`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f4d03f" />
            <stop offset="50%" stopColor="#c9a84c" />
            <stop offset="100%" stopColor="#a08432" />
          </linearGradient>
        </defs>
        <path
          d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"
          fill={active ? `url(#star-grad-${index})` : 'transparent'}
          stroke={active ? '#c9a84c' : 'var(--bk-text-dim)'}
          strokeWidth="1.5"
          strokeLinejoin="round"
          style={{
            transition: 'fill 0.25s ease, stroke 0.25s ease',
          }}
        />
      </svg>
    </button>
  )
}

function AnimatedCheckmark() {
  return (
    <div className="review-checkmark-wrap">
      <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
        <circle
          cx="40"
          cy="40"
          r="36"
          stroke="var(--bk-green)"
          strokeWidth="3"
          fill="none"
          className="review-check-circle"
        />
        <path
          d="M24 40l10 10 22-22"
          stroke="var(--bk-green)"
          strokeWidth="3.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
          className="review-check-path"
        />
      </svg>
    </div>
  )
}

function ShimmerSkeleton() {
  return (
    <div className="review-container" style={{ opacity: 0.7 }}>
      <div className="bk-skeleton" style={{ height: 14, width: '60%', borderRadius: 8, margin: '0 auto' }} />
      <div className="bk-skeleton" style={{ height: 10, width: '40%', borderRadius: 6, margin: '8px auto 0' }} />
      <div
        style={{
          width: 72,
          height: 72,
          borderRadius: '50%',
          margin: '32px auto 0',
        }}
        className="bk-skeleton"
      />
      <div className="bk-skeleton" style={{ height: 18, width: '50%', borderRadius: 8, margin: '16px auto 0' }} />
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 32 }}>
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="bk-skeleton" style={{ width: 48, height: 48, borderRadius: 12 }} />
        ))}
      </div>
    </div>
  )
}

export default function ReviewPublicScreen() {
  const [phase, setPhase] = useState<Phase>('loading')
  const [info, setInfo] = useState<ReviewInfo | null>(null)
  const [rating, setRating] = useState(0)
  const [hoveredStar, setHoveredStar] = useState(0)
  const [comment, setComment] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const params = new URLSearchParams(window.location.search)
  const branchId = params.get('branch')
  const barberId = params.get('barber')
  const visitId = params.get('visit')

  useEffect(() => {
    if (!branchId || !barberId) {
      setPhase('error')
      return
    }

    const alreadySubmitted = localStorage.getItem(`review_${branchId}_${barberId}`)
    if (alreadySubmitted) {
      setPhase('success')
      return
    }

    fetch(`${API_BASE}/reviews/info?branch=${branchId}&barber=${barberId}`)
      .then((res) => {
        if (!res.ok) throw new Error('not found')
        return res.json()
      })
      .then((data: ReviewInfo) => {
        setInfo(data)
        setPhase('form')
      })
      .catch(() => {
        setPhase('error')
      })
  }, [branchId, barberId])

  const handleSubmit = useCallback(async () => {
    if (!rating || !branchId || !barberId) return
    setIsSubmitting(true)
    setSubmitError(null)

    try {
      const body: Record<string, unknown> = {
        branch_id: branchId,
        barber_id: barberId,
        rating,
        comment: comment.trim() || null,
        source: 'form',
      }
      if (visitId) body.visit_id = visitId

      const res = await fetch(`${API_BASE}/reviews/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) throw new Error('submit failed')

      localStorage.setItem(`review_${branchId}_${barberId}`, '1')
      setPhase('success')
    } catch {
      setSubmitError('Не удалось отправить. Попробуйте ещё раз.')
      setIsSubmitting(false)
    }
  }, [rating, comment, branchId, barberId, visitId])

  const ratingLabels = ['', 'Ужасно', 'Плохо', 'Нормально', 'Хорошо', 'Отлично']

  if (phase === 'loading') {
    return (
      <div className="review-page">
        <ShimmerSkeleton />
      </div>
    )
  }

  if (phase === 'error') {
    return (
      <div className="review-page">
        <div className="review-container review-fade-in" style={{ textAlign: 'center', paddingTop: 80 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(229, 69, 69, 0.1)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto',
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="var(--bk-red)" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
          <h2
            style={{
              fontFamily: 'var(--bk-font-heading)',
              fontSize: 22,
              fontWeight: 600,
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              color: 'var(--bk-text)',
              marginTop: 20,
            }}
          >
            Ссылка недействительна
          </h2>
          <p style={{ color: 'var(--bk-text-secondary)', fontSize: 14, marginTop: 8 }}>
            Проверьте правильность ссылки или обратитесь к администратору
          </p>
        </div>
      </div>
    )
  }

  if (phase === 'success') {
    return (
      <div className="review-page">
        <div className="review-container review-fade-in" style={{ textAlign: 'center', paddingTop: 60 }}>
          <AnimatedCheckmark />
          <h2
            style={{
              fontFamily: 'var(--bk-font-heading)',
              fontSize: 26,
              fontWeight: 600,
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              color: 'var(--bk-text)',
              marginTop: 24,
            }}
          >
            Спасибо за отзыв!
          </h2>
          <p
            style={{
              color: 'var(--bk-text-secondary)',
              fontSize: 15,
              marginTop: 12,
              lineHeight: 1.5,
            }}
          >
            Ваше мнение помогает нам стать лучше
          </p>
          <div
            style={{
              marginTop: 40,
              height: 2,
              width: 60,
              borderRadius: 1,
              background: 'linear-gradient(90deg, transparent, var(--bk-gold), transparent)',
              margin: '40px auto 0',
            }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="review-page">
      <div className="review-container review-fade-in">
        {/* Branch info */}
        <div style={{ textAlign: 'center' }}>
          <p
            style={{
              fontSize: 13,
              color: 'var(--bk-text-secondary)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              fontFamily: 'var(--bk-font-heading)',
            }}
          >
            {info?.branch_name}
          </p>
          {info?.branch_address && (
            <p style={{ fontSize: 12, color: 'var(--bk-text-dim)', marginTop: 4 }}>
              {info.branch_address}
            </p>
          )}
        </div>

        {/* Decorative divider */}
        <div
          style={{
            height: 1,
            background: 'linear-gradient(90deg, transparent, var(--bk-border-gold), transparent)',
            margin: '20px 0',
          }}
        />

        {/* Barber avatar placeholder + name */}
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--bk-bg-elevated), var(--bk-bg-card))',
              border: '2px solid var(--bk-border-gold)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto',
              boxShadow: '0 0 30px -8px var(--bk-gold-glow)',
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
              <path
                d="M5.121 17.804A13.937 13.937 0 0112 16c2.5 0 4.847.655 6.879 1.804M15 10a3 3 0 11-6 0 3 3 0 016 0z"
                stroke="var(--bk-gold-dim)"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <h1
            style={{
              fontFamily: 'var(--bk-font-heading)',
              fontSize: 28,
              fontWeight: 600,
              letterSpacing: '0.02em',
              textTransform: 'uppercase',
              color: 'var(--bk-text)',
              marginTop: 14,
            }}
          >
            {info?.barber_name}
          </h1>
          <p style={{ fontSize: 14, color: 'var(--bk-text-secondary)', marginTop: 4 }}>
            Оцените качество обслуживания
          </p>
        </div>

        {/* Stars */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'center',
            gap: 8,
            marginTop: 28,
            padding: '8px 0',
          }}
        >
          {[1, 2, 3, 4, 5].map((star) => (
            <GoldStar
              key={star}
              index={star - 1}
              filled={star <= rating}
              hovered={star <= hoveredStar}
              onSelect={() => setRating(star)}
              onHover={() => setHoveredStar(star)}
              onLeave={() => setHoveredStar(0)}
            />
          ))}
        </div>

        {/* Rating label */}
        <div
          style={{
            textAlign: 'center',
            height: 24,
            marginTop: 8,
            transition: 'opacity 0.2s ease',
            opacity: rating > 0 || hoveredStar > 0 ? 1 : 0,
          }}
        >
          <span
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: 'var(--bk-gold)',
            }}
          >
            {ratingLabels[hoveredStar || rating]}
          </span>
        </div>

        {/* Comment (appears after rating) */}
        <div
          style={{
            overflow: 'hidden',
            maxHeight: rating > 0 ? 200 : 0,
            opacity: rating > 0 ? 1 : 0,
            transition: 'max-height 0.4s ease, opacity 0.3s ease',
            marginTop: 16,
          }}
        >
          <textarea
            className="review-textarea"
            placeholder="Расскажите подробнее (необязательно)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={1000}
            rows={3}
          />
          {comment.length > 0 && (
            <p
              style={{
                textAlign: 'right',
                fontSize: 11,
                color: 'var(--bk-text-dim)',
                marginTop: 4,
              }}
            >
              {comment.length}/1000
            </p>
          )}
        </div>

        {/* Submit error */}
        {submitError && (
          <p style={{ color: 'var(--bk-red)', fontSize: 13, textAlign: 'center', marginTop: 12 }}>
            {submitError}
          </p>
        )}

        {/* Submit button */}
        <button
          type="button"
          className="review-submit"
          disabled={rating === 0 || isSubmitting}
          onClick={handleSubmit}
          style={{
            opacity: rating > 0 ? 1 : 0.4,
            transition: 'opacity 0.3s ease, box-shadow 0.3s ease, transform 0.15s ease',
          }}
        >
          {isSubmitting ? (
            <span className="review-spinner" />
          ) : (
            'Отправить'
          )}
        </button>
      </div>
    </div>
  )
}
