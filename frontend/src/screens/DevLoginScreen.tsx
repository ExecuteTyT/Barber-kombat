import { useEffect, useState } from 'react'

import { authApi, type DevUser } from '../api/client'
import { useAuthStore } from '../stores/authStore'

const ROLE_LABELS: Record<string, string> = {
  barber: 'Барбер',
  chef: 'Шеф',
  owner: 'Владелец',
  admin: 'Администратор',
  manager: 'Менеджер',
}

const ROLE_COLORS: Record<string, string> = {
  barber: 'bg-blue-600',
  chef: 'bg-purple-600',
  owner: 'bg-amber-600',
  admin: 'bg-emerald-600',
  manager: 'bg-indigo-600',
}

export default function DevLoginScreen() {
  const [users, setUsers] = useState<DevUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const devLogin = useAuthStore((s) => s.devLogin)

  useEffect(() => {
    authApi
      .devUsers()
      .then(setUsers)
      .catch(() => setError('Не удалось загрузить пользователей. Запустите seed-demo.'))
      .finally(() => setLoading(false))
  }, [])

  const handleSelect = (telegramId: number) => {
    devLogin(telegramId)
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-950 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold text-white">Barber Kombat</h1>
          <p className="mt-1 text-sm text-gray-400">Dev Mode — выберите пользователя</p>
        </div>

        {loading && (
          <div className="flex justify-center py-8">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-900/30 p-4 text-center text-sm text-red-300">
            {error}
          </div>
        )}

        {!loading && !error && users.length === 0 && (
          <div className="rounded-lg bg-gray-800 p-6 text-center">
            <p className="text-gray-300">Нет пользователей в БД.</p>
            <p className="mt-2 text-sm text-gray-500">
              Выполните: <code className="rounded bg-gray-700 px-1">python -m app.cli seed-demo</code>
            </p>
          </div>
        )}

        {!loading && users.length > 0 && (
          <div className="space-y-2">
            {users.map((u) => (
              <button
                key={u.telegram_id}
                onClick={() => handleSelect(u.telegram_id)}
                className="flex w-full items-center gap-3 rounded-lg bg-gray-800 px-4 py-3 text-left transition-colors hover:bg-gray-700 active:bg-gray-600"
              >
                <span
                  className={`inline-flex min-w-[80px] items-center justify-center rounded-full px-2.5 py-0.5 text-xs font-medium text-white ${ROLE_COLORS[u.role] ?? 'bg-gray-600'}`}
                >
                  {ROLE_LABELS[u.role] ?? u.role}
                </span>
                <span className="flex-1 text-sm font-medium text-white">{u.name}</span>
                <span className="text-xs text-gray-500">{u.telegram_id}</span>
              </button>
            ))}
          </div>
        )}

        <p className="mt-6 text-center text-xs text-gray-600">
          Этот экран доступен только в dev-режиме (APP_ENV=development)
        </p>
      </div>
    </div>
  )
}
