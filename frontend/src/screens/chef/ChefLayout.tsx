import { Outlet } from 'react-router-dom'

import TabBar from '../../components/TabBar'
import type { TabItem } from '../../types'

const tabs: TabItem[] = [
  { path: '/chef/kombat', label: 'Комбат', icon: '\u{2694}\u{FE0F}' },
  { path: '/chef/branch', label: 'Филиал', icon: '\u{1F3EA}' },
  { path: '/chef/pvr', label: 'ПВР', icon: '\u{1F4C8}' },
  { path: '/chef/more', label: 'Ещё', icon: '\u{2699}\u{FE0F}' },
]

export default function ChefLayout() {
  return (
    <div className="min-h-screen pb-16">
      <Outlet />
      <TabBar items={tabs} />
    </div>
  )
}
