import { useEffect } from 'react'
import { backButton } from '@telegram-apps/sdk-react'

interface TelegramBackButtonProps {
  onClick: () => void
}

export default function TelegramBackButton({ onClick }: TelegramBackButtonProps) {
  useEffect(() => {
    if (backButton.mount.isAvailable()) {
      backButton.mount()
    }
    if (backButton.show.isAvailable()) {
      backButton.show()
    }

    const off = backButton.onClick.isAvailable()
      ? backButton.onClick(onClick)
      : undefined

    return () => {
      off?.()
      if (backButton.hide.isAvailable()) {
        backButton.hide()
      }
    }
  }, [onClick])

  return null
}
