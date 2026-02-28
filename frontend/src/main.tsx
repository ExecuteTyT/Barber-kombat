import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { init } from '@telegram-apps/sdk-react'

import ErrorBoundary from './components/ErrorBoundary'
import App from './App'
import './index.css'

// Initialize Telegram Mini Apps SDK only when running inside Telegram
const isTelegram = Boolean(window.Telegram?.WebApp?.initData)

if (isTelegram) {
  try {
    init()
  } catch {
    console.warn('Telegram SDK init failed')
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
