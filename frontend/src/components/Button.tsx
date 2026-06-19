import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]',
  secondary: 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]',
}

/**
 * Shared action button. Encapsulates the gold / secondary variants, the 44px
 * touch target, consistent radius (rounded-xl) and disabled styling used across
 * the app — so call sites only express intent (variant) and layout (className).
 */
export default function Button({
  variant = 'primary',
  type = 'button',
  className = '',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={`min-h-[44px] rounded-xl px-4 py-3 text-sm font-semibold transition-colors disabled:opacity-50 ${VARIANTS[variant]}${
        className ? ` ${className}` : ''
      }`}
      {...props}
    />
  )
}
