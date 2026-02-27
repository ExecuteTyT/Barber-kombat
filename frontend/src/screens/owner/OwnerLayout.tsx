import { Outlet } from 'react-router-dom'

import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/owner/dashboard', label: 'Дашборд', icon: '\u{1F3E0}' },
  { path: '/owner/reports', label: 'Отчёты', icon: '\u{1F4CA}' },
  { path: '/owner/competitions', label: 'Комбат', icon: '\u{2694}\u{FE0F}' },
  { path: '/owner/settings', label: 'Настройки', icon: '\u{2699}\u{FE0F}' },
]

export default function OwnerLayout() {
  return (
    <div className="min-h-screen pb-16">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
