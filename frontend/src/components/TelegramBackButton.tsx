import { useEffect } from 'react'

interface TelegramBackButtonProps {
  onClick: () => void
}

export default function TelegramBackButton({ onClick }: TelegramBackButtonProps) {
  useEffect(() => {
    const btn = window.Telegram?.WebApp?.BackButton
    if (!btn) return

    btn.show()
    btn.onClick(onClick)

    return () => {
      btn.offClick(onClick)
      btn.hide()
    }
  }, [onClick])

  return null
}
