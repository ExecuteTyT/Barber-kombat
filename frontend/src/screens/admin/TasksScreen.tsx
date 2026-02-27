import { useEffect, useState } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAdminStore } from '../../stores/adminStore'
import { useAuthStore } from '../../stores/authStore'
import type { UnconfirmedRecord, UnfilledBirthday, UnprocessedCheck } from '../../types'

function formatTime(datetime: string): string {
  try {
    const d = new Date(datetime)
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return datetime
  }
}

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

// --- Unconfirmed records section ---
function UnconfirmedSection({
  records,
  onConfirmAll,
  confirming,
}: {
  records: UnconfirmedRecord[]
  onConfirmAll: () => void
  confirming: boolean
}) {
  const count = records.length
  return (
    <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]">
      <div className="flex items-center justify-between px-4 pb-1 pt-3">
        <div className="flex items-center gap-2">
          {count > 0 ? (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-xs font-bold text-white">
              {count}
            </span>
          ) : (
            <span className="text-emerald-500">{'\u{2705}'}</span>
          )}
          <span className="text-sm font-medium">Неподтверждённые записи на завтра</span>
        </div>
        {count > 0 && (
          <button
            type="button"
            className="rounded-lg bg-[var(--tg-theme-button-color)] px-3 py-1 text-xs font-medium text-[var(--tg-theme-button-text-color)] disabled:opacity-50"
            onClick={onConfirmAll}
            disabled={confirming}
          >
            {confirming ? 'Подтверждение...' : 'Подтвердить все'}
          </button>
        )}
      </div>
      {count > 0 && (
        <div className="divide-y divide-[var(--tg-theme-hint-color)]/10 px-4 pb-2">
          {records.map((r) => (
            <div key={r.record_id} className="flex items-center justify-between py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{r.client_name}</p>
                <p className="text-xs text-[var(--tg-theme-hint-color)]">
                  {r.service_name} {'\u{2022}'} {r.barber_name}
                </p>
              </div>
              <span className="ml-2 text-sm tabular-nums text-[var(--tg-theme-hint-color)]">
                {formatTime(r.datetime)}
              </span>
            </div>
          ))}
        </div>
      )}
      {count === 0 && (
        <p className="px-4 pb-3 text-sm text-[var(--tg-theme-hint-color)]">Все записи подтверждены</p>
      )}
    </div>
  )
}

// --- Unfilled birthdays section ---
function BirthdaysSection({ clients }: { clients: UnfilledBirthday[] }) {
  const count = clients.length
  return (
    <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]">
      <div className="flex items-center gap-2 px-4 pb-1 pt-3">
        {count > 0 ? (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1.5 text-xs font-bold text-white">
            {count}
          </span>
        ) : (
          <span className="text-emerald-500">{'\u{2705}'}</span>
        )}
        <span className="text-sm font-medium">Незаполненные ДР</span>
      </div>
      {count > 0 && (
        <div className="divide-y divide-[var(--tg-theme-hint-color)]/10 px-4 pb-2">
          {clients.map((c) => (
            <div key={c.client_id} className="flex items-center justify-between py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm">{c.client_name}</p>
                {c.last_visit && (
                  <p className="text-xs text-[var(--tg-theme-hint-color)]">
                    Последний визит: {c.last_visit}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {count === 0 && (
        <p className="px-4 pb-3 text-sm text-[var(--tg-theme-hint-color)]">Все ДР заполнены</p>
      )}
    </div>
  )
}

// --- Unprocessed checks section ---
function ChecksSection({ checks }: { checks: UnprocessedCheck[] }) {
  const count = checks.length
  if (count === 0) return null

  return (
    <div className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)]">
      <div className="flex items-center gap-2 px-4 pb-1 pt-3">
        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-orange-500 px-1.5 text-xs font-bold text-white">
          {count}
        </span>
        <span className="text-sm font-medium">Непроведённые чеки</span>
      </div>
      <div className="divide-y divide-[var(--tg-theme-hint-color)]/10 px-4 pb-2">
        {checks.map((ch) => (
          <div key={ch.record_id} className="flex items-center justify-between py-2">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">{ch.client_name}</p>
              <p className="text-xs text-[var(--tg-theme-hint-color)]">
                {ch.barber_name} {'\u{2022}'} {ch.status}
              </p>
            </div>
            <span className="ml-2 text-sm font-bold tabular-nums">{formatMoney(ch.amount)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function TasksScreen() {
  const { user } = useAuthStore()
  const { tasks, loading, error, fetchTasks, confirmRecords } = useAdminStore()
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    if (user?.branch_id) {
      fetchTasks(user.branch_id)
    }
  }, [user?.branch_id, fetchTasks])

  const handleConfirmAll = async () => {
    if (!tasks || !user?.branch_id) return
    const ids = tasks.unconfirmed_records.map((r) => r.record_id)
    if (ids.length === 0) return
    setConfirming(true)
    await confirmRecords(user.branch_id, ids)
    setConfirming(false)
  }

  if (loading && !tasks) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="text-lg font-bold">Задачи</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="text-lg font-bold">Задачи</h1>
        <p className="mt-4 text-center text-sm text-red-500">{error}</p>
      </div>
    )
  }

  if (!tasks) return null

  const totalPending =
    tasks.unconfirmed_records.length +
    tasks.unfilled_birthdays.length +
    tasks.unprocessed_checks.length

  return (
    <div className="pb-4 pt-4">
      <div className="flex items-baseline justify-between px-4">
        <h1 className="text-lg font-bold">Задачи</h1>
        {totalPending > 0 ? (
          <span className="text-sm text-[var(--tg-theme-hint-color)]">
            {totalPending} {totalPending === 1 ? 'задача' : 'задач'}
          </span>
        ) : (
          <span className="text-sm text-emerald-500">Всё выполнено</span>
        )}
      </div>
      <p className="mt-1 px-4 text-xs text-[var(--tg-theme-hint-color)]">{tasks.date}</p>

      <div className="mx-4 mt-4 space-y-3">
        <UnconfirmedSection
          records={tasks.unconfirmed_records}
          onConfirmAll={handleConfirmAll}
          confirming={confirming}
        />
        <BirthdaysSection clients={tasks.unfilled_birthdays} />
        <ChecksSection checks={tasks.unprocessed_checks} />
      </div>
    </div>
  )
}
