import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-4 text-center">
          <p className="text-lg font-medium text-[var(--tg-theme-text-color)]">
            Что-то пошло не так
          </p>
          <p className="text-sm text-[var(--tg-theme-hint-color)]">{this.state.error?.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg bg-[var(--tg-theme-button-color)] px-6 py-2 text-[var(--tg-theme-button-text-color)]"
          >
            Попробовать снова
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
