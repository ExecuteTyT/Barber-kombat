import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { init } from '@telegram-apps/sdk-react'

import ErrorBoundary from './components/ErrorBoundary'
import App from './App'
import './index.css'

// Initialize Telegram Mini Apps SDK
try {
  init()
} catch {
  // SDK init may fail outside Telegram — app still works for dev
  console.warn('Telegram SDK init failed — running outside Telegram?')
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
