import { useEffect, useState } from 'react'

import { authApi, type DevUser } from '../api/client'
import { IconScissors } from '../components/Icons'
import { useAuthStore } from '../stores/authStore'

const ROLE_LABELS: Record<string, string> = {
  barber: 'Барбер',
  owner: 'Владелец',
  admin: 'Администратор',
}

const ROLE_COLORS: Record<string, string> = {
  barber: 'bg-[var(--bk-gold)]/20 text-[var(--bk-gold)]',
  owner: 'bg-[var(--bk-gold-bright)]/20 text-[var(--bk-gold-bright)]',
  admin: 'bg-[var(--bk-green)]/20 text-[var(--bk-green)]',
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
    <div className="flex min-h-screen flex-col items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--bk-gold)]/10 text-[var(--bk-gold)]">
            <IconScissors size={32} />
          </div>
          <h1 className="bk-heading text-3xl text-[var(--bk-text)]">MAKON</h1>
          <p className="mt-2 text-sm text-[var(--bk-text-secondary)]">
            Dev Mode — выберите пользователя
          </p>
        </div>

        {loading && (
          <div className="flex justify-center py-8">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--bk-gold)] border-t-transparent" />
          </div>
        )}

        {error && (
          <div className="bk-card border-[var(--bk-red)]/20 p-4 text-center text-sm text-[var(--bk-red)]">
            {error}
          </div>
        )}

        {!loading && !error && users.length === 0 && (
          <div className="bk-card p-6 text-center">
            <p className="text-[var(--bk-text)]">Нет пользователей в БД.</p>
            <p className="mt-2 text-sm text-[var(--bk-text-secondary)]">
              Выполните:{' '}
              <code className="rounded bg-[var(--bk-bg-elevated)] px-1.5 py-0.5 text-[var(--bk-gold)]">
                python -m app.cli seed-demo
              </code>
            </p>
          </div>
        )}

        {!loading && users.length > 0 && (
          <div className="space-y-2">
            {users.map((u, i) => (
              <button
                key={u.telegram_id}
                onClick={() => handleSelect(u.telegram_id)}
                className="bk-card flex w-full items-center gap-3 px-4 py-3.5 text-left transition-all active:scale-[0.98] bk-fade-up"
                style={{ animationDelay: `${i * 50}ms` }}
              >
                <span
                  className={`inline-flex min-w-[80px] items-center justify-center rounded-full px-2.5 py-1 text-xs font-semibold ${ROLE_COLORS[u.role] ?? 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-dim)]'}`}
                >
                  {ROLE_LABELS[u.role] ?? u.role}
                </span>
                <span className="flex-1 text-sm font-medium text-[var(--bk-text)]">{u.name}</span>
                <span className="text-xs text-[var(--bk-text-dim)]">{u.telegram_id}</span>
              </button>
            ))}
          </div>
        )}

        <p className="mt-8 text-center text-xs text-[var(--bk-text-dim)]">
          Этот экран доступен только в dev-режиме (APP_ENV=development)
        </p>
      </div>
    </div>
  )
}
