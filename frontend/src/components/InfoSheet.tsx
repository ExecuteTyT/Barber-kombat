import { useEffect, useRef, type ReactNode } from 'react'

import { IconX } from './Icons'

interface InfoSheetProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
}

export default function InfoSheet({ open, onClose, title, children }: InfoSheetProps) {
  const backdropRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  if (!open) return null

  return (
    <div
      ref={backdropRef}
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 backdrop-blur-sm bk-fade-in"
      onClick={(e) => {
        if (e.target === backdropRef.current) onClose()
      }}
    >
      <div className="bk-slide-up w-full max-w-lg rounded-t-2xl bg-[var(--bk-bg-primary)] pb-8">
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="h-1 w-10 rounded-full bg-[var(--bk-text-dim)]/30" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pb-3 pt-1">
          <h2
            className="text-lg font-bold text-[var(--bk-text)]"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-[var(--bk-text-dim)] active:bg-[var(--bk-bg-elevated)]"
          >
            <IconX size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[65vh] overflow-y-auto px-5">{children}</div>
      </div>
    </div>
  )
}

export function InfoButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--bk-bg-elevated)] text-xs font-bold text-[var(--bk-text-secondary)] active:bg-[var(--bk-border)]"
    >
      ?
    </button>
  )
}

export function InfoSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mb-4 last:mb-0">
      <h3 className="mb-1.5 text-sm font-semibold text-[var(--bk-gold)]">{title}</h3>
      <div className="text-sm leading-relaxed text-[var(--bk-text-secondary)]">{children}</div>
    </div>
  )
}

export function InfoMetricRow({
  color,
  label,
  weight,
  description,
}: {
  color: string
  label: string
  weight: number
  description: string
}) {
  return (
    <div className="flex items-start gap-2.5 py-1.5">
      <span className={`mt-1.5 h-2.5 w-2.5 flex-shrink-0 rounded-full ${color}`} />
      <div>
        <span className="text-sm font-medium text-[var(--bk-text)]">
          {label} <span className="font-normal text-[var(--bk-text-dim)]">({weight}%)</span>
        </span>
        <p className="text-xs leading-relaxed text-[var(--bk-text-secondary)]">{description}</p>
      </div>
    </div>
  )
}
