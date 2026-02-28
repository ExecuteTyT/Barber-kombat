import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

import { IconAlertCircle } from './Icons'

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
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--bk-red)]/10">
            <IconAlertCircle size={28} className="text-[var(--bk-red)]" />
          </div>
          <p className="bk-heading text-xl text-[var(--bk-text)]">Что-то пошло не так</p>
          <p className="text-sm text-[var(--bk-text-secondary)]">{this.state.error?.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-2 rounded-xl bg-[var(--bk-gold)] px-8 py-2.5 text-sm font-semibold text-[var(--bk-bg-primary)]"
          >
            Попробовать снова
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
