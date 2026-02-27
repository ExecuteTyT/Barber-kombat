import { useEffect, useCallback } from 'react'

import { useAuthStore } from '../stores/authStore'
import { useKombatStore } from '../stores/kombatStore'
import { useWebSocket } from './useWebSocket'
import type { RatingEntry, WSMessage } from '../types'

/**
 * Loads today's kombat rating for the current barber's branch
 * and subscribes to real-time WebSocket updates.
 */
export function useKombatRating() {
  const user = useAuthStore((s) => s.user)
  const { todayRating, isLoading, error, fetchTodayRating, applyRatingUpdate } = useKombatStore()

  const branchId = user?.branch_id

  // Fetch on mount
  useEffect(() => {
    if (branchId) {
      fetchTodayRating(branchId)
    }
  }, [branchId, fetchTodayRating])

  // Handle real-time updates
  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      if (message.type === 'rating_update') {
        const data = message.data as {
          branch_id?: string
          ratings?: RatingEntry[]
        }
        // Only apply if it matches our branch
        if (data.branch_id === branchId && data.ratings) {
          applyRatingUpdate(data.ratings)
        }
      }
    },
    [branchId, applyRatingUpdate],
  )

  useWebSocket(handleWSMessage)

  const refresh = useCallback(() => {
    if (branchId) {
      fetchTodayRating(branchId)
    }
  }, [branchId, fetchTodayRating])

  return { todayRating, isLoading, error, refresh }
}
