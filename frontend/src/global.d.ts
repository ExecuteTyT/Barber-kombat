interface TelegramWebApp {
  initData: string
  initDataUnsafe: Record<string, unknown>
  themeParams: Record<string, string>
  close: () => void
  expand: () => void
  ready: () => void
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp
  }
}
