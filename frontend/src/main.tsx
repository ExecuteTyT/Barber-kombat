import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import ErrorBoundary from './components/ErrorBoundary'
import App from './App'
import './index.css'

// Signal to Telegram that the Mini App is ready and expand to full screen
window.Telegram?.WebApp?.ready()
window.Telegram?.WebApp?.expand()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
