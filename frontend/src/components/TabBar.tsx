import { NavLink } from 'react-router-dom'

import type { TabItem } from '../types'

interface TabBarProps {
  items: TabItem[]
}

export default function TabBar({ items }: TabBarProps) {
  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 flex border-t border-[var(--tg-theme-hint-color)]/20 bg-[var(--tg-theme-bg-color)]"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      {items.map((item) => (
        <NavLink
          key={item.path}
          to={item.path}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-0.5 py-2 text-xs transition-colors ${
              isActive ? 'text-[var(--tg-theme-button-color)]' : 'text-[var(--tg-theme-hint-color)]'
            }`
          }
        >
          <span className="text-lg">{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
