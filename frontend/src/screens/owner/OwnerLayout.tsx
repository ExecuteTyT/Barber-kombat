import { Outlet } from 'react-router-dom'

import { IconHome, IconBarChart, IconSwords, IconGear } from '../../components/Icons'
import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/owner/dashboard', label: 'Дашборд', icon: <IconHome size={20} /> },
  { path: '/owner/reports', label: 'Отчёты', icon: <IconBarChart size={20} /> },
  { path: '/owner/competitions', label: 'Комбат', icon: <IconSwords size={20} /> },
  { path: '/owner/settings', label: 'Настройки', icon: <IconGear size={20} /> },
]

export default function OwnerLayout() {
  return (
    <div className="min-h-screen pb-20">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
