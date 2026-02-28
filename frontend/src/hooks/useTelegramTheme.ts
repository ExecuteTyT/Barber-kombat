import { useEffect } from 'react'
import { mountThemeParams, bindThemeParamsCssVars } from '@telegram-apps/sdk-react'

const isTelegram = Boolean(window.Telegram?.WebApp?.initData)

/**
 * Mounts Telegram theme params and binds them as CSS variables
 * on the document root (e.g. --tg-theme-bg-color).
 *
 * Falls back to defaults defined in index.css when outside Telegram.
 */
export function useTelegramTheme() {
  useEffect(() => {
    if (!isTelegram) return

    let unbind: VoidFunction | undefined

    if (mountThemeParams.isAvailable()) {
      mountThemeParams()
    }

    if (bindThemeParamsCssVars.isAvailable()) {
      unbind = bindThemeParamsCssVars()
    }

    return () => {
      unbind?.()
    }
  }, [])
}
