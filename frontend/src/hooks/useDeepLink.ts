import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

import type { UserRole } from '../types'

interface DeepLinkTarget {
  path: string
  state?: Record<string, unknown>
}

function resolveDeepLink(startParam: string, role: UserRole): DeepLinkTarget | null {
  const kombatMatch = startParam.match(/^kombat_(.+)$/)
  if (kombatMatch) {
    const branchId = kombatMatch[1]
    switch (role) {
      case 'barber':
        return { path: '/barber/kombat' }
      case 'owner':
        return { path: `/owner/branch/${branchId}` }
      case 'admin':
        return { path: '/admin/metrics' }
    }
  }

  const reviewMatch = startParam.match(/^review_(.+)$/)
  if (reviewMatch) {
    const reviewId = reviewMatch[1]
    if (role === 'owner') {
      return { path: '/owner/dashboard', state: { reviewId } }
    }
    return null
  }

  const reportMatch = startParam.match(/^report_([a-z-]+)_(\d{4}-\d{2}-\d{2})$/)
  if (reportMatch) {
    if (role === 'owner') {
      return { path: '/owner/reports', state: { reportType: reportMatch[1], reportDate: reportMatch[2] } }
    }
    return null
  }

  return null
}

function getStartParam(): string | undefined {
  // Read startapp param directly from Telegram WebApp — no SDK hook needed
  const unsafe = window.Telegram?.WebApp?.initDataUnsafe as Record<string, unknown> | undefined
  const param = unsafe?.start_param
  return typeof param === 'string' ? param : undefined
}

export function useDeepLink(role: UserRole | undefined): void {
  const navigate = useNavigate()
  const consumed = useRef(false)
  const startParam = getStartParam()

  useEffect(() => {
    if (consumed.current || !startParam || !role) return
    consumed.current = true

    const target = resolveDeepLink(startParam, role)
    if (target) {
      navigate(target.path, { replace: true, state: target.state })
    }
  }, [startParam, role, navigate])
}
