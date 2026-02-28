import { NavLink } from 'react-router-dom'

import type { TabItem } from '../types'

interface TabBarProps {
  items: TabItem[]
}

export default function TabBar({ items }: TabBarProps) {
  return (
    <nav
      className="bk-tab-bar fixed bottom-0 left-0 right-0 z-50 flex"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {items.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium tracking-wide transition-colors ${
              isActive ? 'text-[var(--bk-gold)]' : 'text-[var(--bk-text-dim)]'
            }`
          }
        >
          <span className="flex h-5 w-5 items-center justify-center">{item.icon}</span>
          <span className="uppercase">{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
