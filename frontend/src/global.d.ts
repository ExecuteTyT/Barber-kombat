interface TelegramWebApp {
  initData: string
  initDataUnsafe: {
    start_param?: string
    user?: Record<string, unknown>
    [key: string]: unknown
  }
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
