import { Outlet } from 'react-router-dom'

import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/barber/kombat', label: 'Комбат', icon: '\u{2694}\u{FE0F}' },
  { path: '/barber/progress', label: 'Прогресс', icon: '\u{1F4C8}' },
  { path: '/barber/history', label: 'История', icon: '\u{1F4C5}' },
]

export default function BarberLayout() {
  return (
    <div className="min-h-screen pb-16">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
