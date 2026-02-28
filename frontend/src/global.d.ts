interface TelegramBackButton {
  isVisible: boolean
  onClick: (cb: () => void) => void
  offClick: (cb: () => void) => void
  show: () => void
  hide: () => void
}

interface TelegramWebApp {
  initData: string
  initDataUnsafe: {
    start_param?: string
    user?: Record<string, unknown>
    [key: string]: unknown
  }
  themeParams: Record<string, string>
  BackButton: TelegramBackButton
  close: () => void
  expand: () => void
  ready: () => void
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp
  }
}
