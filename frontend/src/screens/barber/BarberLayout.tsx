import { Outlet } from 'react-router-dom'

import { IconSwords, IconTrendingUp, IconCalendar } from '../../components/Icons'
import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/barber/kombat', label: 'Комбат', icon: <IconSwords size={20} /> },
  { path: '/barber/progress', label: 'Прогресс', icon: <IconTrendingUp size={20} /> },
  { path: '/barber/history', label: 'История', icon: <IconCalendar size={20} /> },
]

export default function BarberLayout() {
  return (
    <div className="min-h-screen pb-20">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
