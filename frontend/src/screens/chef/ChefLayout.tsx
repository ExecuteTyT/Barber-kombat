import { Outlet } from 'react-router-dom'

import { IconSwords, IconBuilding, IconTrendingUp, IconBarChart } from '../../components/Icons'
import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/chef/kombat', label: 'Комбат', icon: <IconSwords size={20} /> },
  { path: '/chef/branch', label: 'Филиал', icon: <IconBuilding size={20} /> },
  { path: '/chef/pvr', label: 'ПВР', icon: <IconTrendingUp size={20} /> },
  { path: '/chef/analytics', label: 'Аналитика', icon: <IconBarChart size={20} /> },
]

export default function ChefLayout() {
  return (
    <div className="min-h-screen pb-20">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
