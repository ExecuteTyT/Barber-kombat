import { useEffect, useCallback } from 'react'

import { useAuthStore } from '../stores/authStore'
import { usePvrStore } from '../stores/pvrStore'

/**
 * Loads PVR progress for the current barber and threshold configuration.
 */
export function usePVRProgress() {
  const user = useAuthStore((s) => s.user)
  const { barberPvr, thresholds, isLoading, error, fetchBarberPvr, fetchThresholds } = usePvrStore()

  const barberId = user?.id

  useEffect(() => {
    if (barberId) {
      fetchBarberPvr(barberId)
      fetchThresholds()
    }
  }, [barberId, fetchBarberPvr, fetchThresholds])

  const refresh = useCallback(() => {
    if (barberId) {
      fetchBarberPvr(barberId)
    }
  }, [barberId, fetchBarberPvr])

  return { barberPvr, thresholds, isLoading, error, refresh }
}
