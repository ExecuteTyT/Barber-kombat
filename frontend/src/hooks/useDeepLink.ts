import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useLaunchParams } from '@telegram-apps/sdk-react'

import type { UserRole } from '../types'

interface DeepLinkTarget {
  path: string
  state?: Record<string, unknown>
}

/**
 * Parses `startapp` parameter from Telegram deep link and returns a target route.
 *
 * Supported formats:
 *   kombat_{branch_id}    → Kombat screen for the branch
 *   review_{review_id}    → Branch screen focused on reviews
 *   report_{type}_{date}  → Reports screen with pre-selected report
 */
function resolveDeepLink(startParam: string, role: UserRole): DeepLinkTarget | null {
  // kombat_{branch_id}
  const kombatMatch = startParam.match(/^kombat_(.+)$/)
  if (kombatMatch) {
    const branchId = kombatMatch[1]
    switch (role) {
      case 'barber':
        return { path: '/barber/kombat' }
      case 'chef':
      case 'manager':
        return { path: '/chef/kombat' }
      case 'owner':
        return { path: `/owner/branch/${branchId}` }
      case 'admin':
        return { path: '/admin/metrics' }
    }
  }

  // review_{review_id}
  const reviewMatch = startParam.match(/^review_(.+)$/)
  if (reviewMatch) {
    const reviewId = reviewMatch[1]
    switch (role) {
      case 'chef':
      case 'manager':
        return { path: '/chef/branch', state: { reviewId } }
      case 'owner':
        return { path: '/owner/dashboard', state: { reviewId } }
      default:
        return null
    }
  }

  // report_{type}_{date}  e.g. report_revenue_2024-10-13
  const reportMatch = startParam.match(/^report_([a-z-]+)_(\d{4}-\d{2}-\d{2})$/)
  if (reportMatch) {
    const reportType = reportMatch[1]
    if (role === 'owner' || role === 'manager') {
      return { path: '/owner/reports', state: { reportType, reportDate: reportMatch[2] } }
    }
    return null
  }

  return null
}

/**
 * Reads the Telegram `startapp` parameter and navigates to the corresponding screen
 * on first mount after authentication.
 */
export function useDeepLink(role: UserRole | undefined): void {
  const navigate = useNavigate()
  const consumed = useRef(false)

  let startParam: string | undefined
  try {
    const lp = useLaunchParams()
    startParam = lp.tgWebAppStartParam
  } catch {
    // Outside Telegram — no launch params
  }

  useEffect(() => {
    if (consumed.current || !startParam || !role) return
    consumed.current = true

    const target = resolveDeepLink(startParam, role)
    if (target) {
      navigate(target.path, { replace: true, state: target.state })
    }
  }, [startParam, role, navigate])
}
