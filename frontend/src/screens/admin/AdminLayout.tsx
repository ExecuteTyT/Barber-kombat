import { Outlet } from 'react-router-dom'

import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/admin/metrics', label: 'Показатели', icon: '\u{1F4CB}' },
  { path: '/admin/tasks', label: 'Задачи', icon: '\u{2705}' },
  { path: '/admin/history', label: 'История', icon: '\u{1F4C5}' },
]

export default function AdminLayout() {
  return (
    <div className="min-h-screen pb-16">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
