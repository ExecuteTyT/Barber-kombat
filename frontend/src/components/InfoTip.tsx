import { useEffect, useRef, useState } from 'react'

/** A small tappable "ⓘ" that toggles an explanatory popover. Tap-friendly for
 * the Telegram Mini App (no hover). Closes on outside tap. */
export default function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('click', onDoc)
    return () => document.removeEventListener('click', onDoc)
  }, [open])

  return (
    <span ref={ref} className="relative inline-flex align-middle">
      <button
        type="button"
        aria-label="Пояснение"
        onClick={(e) => {
          e.stopPropagation()
          setOpen((v) => !v)
        }}
        className="ml-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-[var(--bk-text-dim)] text-[10px] font-bold leading-none text-[var(--bk-text-dim)]"
      >
        i
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-[70] mb-1.5 w-52 -translate-x-1/2 rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-primary)] p-2.5 text-[11px] font-normal leading-snug text-[var(--bk-text-secondary)] shadow-xl"
        >
          {text}
        </span>
      )}
    </span>
  )
}
