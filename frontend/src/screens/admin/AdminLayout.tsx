import { Outlet } from 'react-router-dom'

import { IconClipboard, IconCheckSquare, IconCalendar } from '../../components/Icons'
import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/admin/metrics', label: 'Показатели', icon: <IconClipboard size={20} /> },
  { path: '/admin/tasks', label: 'Задачи', icon: <IconCheckSquare size={20} /> },
  { path: '/admin/history', label: 'История', icon: <IconCalendar size={20} /> },
]

export default function AdminLayout() {
  return (
    <div className="min-h-screen pb-20">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
