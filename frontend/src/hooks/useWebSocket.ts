import { useEffect, useRef, useCallback } from 'react'

import { useAuthStore } from '../stores/authStore'
import type { WSMessage } from '../types'

type MessageHandler = (message: WSMessage) => void

const PING_INTERVAL = 25_000
const RECONNECT_BASE_DELAY = 1_000
const RECONNECT_MAX_DELAY = 30_000

/**
 * Manages a WebSocket connection to the backend.
 * Handles authentication, automatic reconnection with exponential backoff,
 * and keepalive ping/pong.
 */
export function useWebSocket(onMessage: MessageHandler) {
  const token = useAuthStore((s) => s.token)
  const wsRef = useRef<WebSocket | null>(null)
  const pingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptRef = useRef(0)
  const mountedRef = useRef(true)
  const onMessageRef = useRef(onMessage)

  // Keep the handler reference fresh without re-triggering the effect
  useEffect(() => {
    onMessageRef.current = onMessage
  })

  const connectRef = useRef<() => void>(() => {})

  const clearTimers = useCallback(() => {
    if (pingTimerRef.current) {
      clearInterval(pingTimerRef.current)
      pingTimerRef.current = null
    }
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (!token || !mountedRef.current) return

    // Build WebSocket URL: use VITE_WS_URL if set (cross-origin), else same host
    const wsBase =
      import.meta.env.VITE_WS_URL ??
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    const url = `${wsBase}/ws?token=${encodeURIComponent(token)}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!mountedRef.current) {
        ws.close()
        return
      }
      reconnectAttemptRef.current = 0

      // Start keepalive pings
      pingTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, PING_INTERVAL)
    }

    ws.onmessage = (event) => {
      if (event.data === 'pong') return

      try {
        const message = JSON.parse(event.data) as WSMessage
        onMessageRef.current(message)
      } catch {
        // Ignore malformed messages
      }
    }

    ws.onclose = () => {
      clearTimers()
      wsRef.current = null

      if (!mountedRef.current || !token) return

      // Exponential backoff reconnection
      const attempt = reconnectAttemptRef.current
      const delay = Math.min(RECONNECT_BASE_DELAY * 2 ** attempt, RECONNECT_MAX_DELAY)
      reconnectAttemptRef.current = attempt + 1

      reconnectTimerRef.current = setTimeout(() => {
        if (mountedRef.current) {
          connectRef.current()
        }
      }, delay)
    }

    ws.onerror = () => {
      // onclose will fire after onerror, reconnect handled there
    }
  }, [token, clearTimers])

  useEffect(() => {
    connectRef.current = connect
  })

  useEffect(() => {
    mountedRef.current = true
    connect()

    return () => {
      mountedRef.current = false
      clearTimers()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, clearTimers])
}
