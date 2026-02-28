import { useEffect, useState } from 'react'

import { IconCheckCircle } from '../../components/Icons'
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
    <div className="bk-card overflow-hidden">
      <div className="flex items-center justify-between px-4 pb-1 pt-3">
        <div className="flex items-center gap-2">
          {count > 0 ? (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--bk-red)] px-1.5 text-xs font-bold text-white">
              {count}
            </span>
          ) : (
            <IconCheckCircle size={18} className="text-[var(--bk-green)]" />
          )}
          <span className="text-sm font-medium text-[var(--bk-text)]">
            Неподтверждённые записи на завтра
          </span>
        </div>
        {count > 0 && (
          <button
            type="button"
            className="rounded-lg bg-[var(--bk-gold)] px-3 py-1 text-xs font-semibold text-[var(--bk-bg-primary)] disabled:opacity-50"
            onClick={onConfirmAll}
            disabled={confirming}
          >
            {confirming ? 'Подтверждение...' : 'Подтвердить все'}
          </button>
        )}
      </div>
      {count > 0 && (
        <div className="divide-y divide-[var(--bk-border)] px-4 pb-2">
          {records.map((r) => (
            <div key={r.record_id} className="flex items-center justify-between py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-[var(--bk-text)]">{r.client_name}</p>
                <p className="text-xs text-[var(--bk-text-dim)]">
                  {r.service_name} \u{2022} {r.barber_name}
                </p>
              </div>
              <span className="ml-2 text-sm tabular-nums text-[var(--bk-text-secondary)]">
                {formatTime(r.datetime)}
              </span>
            </div>
          ))}
        </div>
      )}
      {count === 0 && (
        <p className="px-4 pb-3 text-sm text-[var(--bk-text-secondary)]">Все записи подтверждены</p>
      )}
    </div>
  )
}

function BirthdaysSection({ clients }: { clients: UnfilledBirthday[] }) {
  const count = clients.length
  return (
    <div className="bk-card overflow-hidden">
      <div className="flex items-center gap-2 px-4 pb-1 pt-3">
        {count > 0 ? (
          <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--bk-gold)] px-1.5 text-xs font-bold text-[var(--bk-bg-primary)]">
            {count}
          </span>
        ) : (
          <IconCheckCircle size={18} className="text-[var(--bk-green)]" />
        )}
        <span className="text-sm font-medium text-[var(--bk-text)]">Незаполненные ДР</span>
      </div>
      {count > 0 && (
        <div className="divide-y divide-[var(--bk-border)] px-4 pb-2">
          {clients.map((c) => (
            <div key={c.client_id} className="flex items-center justify-between py-2.5">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-[var(--bk-text)]">{c.client_name}</p>
                {c.last_visit && (
                  <p className="text-xs text-[var(--bk-text-dim)]">
                    Последний визит: {c.last_visit}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
      {count === 0 && (
        <p className="px-4 pb-3 text-sm text-[var(--bk-text-secondary)]">Все ДР заполнены</p>
      )}
    </div>
  )
}

function ChecksSection({ checks }: { checks: UnprocessedCheck[] }) {
  const count = checks.length
  if (count === 0) return null

  return (
    <div className="bk-card overflow-hidden">
      <div className="flex items-center gap-2 px-4 pb-1 pt-3">
        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-[var(--bk-bronze)] px-1.5 text-xs font-bold text-white">
          {count}
        </span>
        <span className="text-sm font-medium text-[var(--bk-text)]">Непроведённые чеки</span>
      </div>
      <div className="divide-y divide-[var(--bk-border)] px-4 pb-2">
        {checks.map((ch) => (
          <div key={ch.record_id} className="flex items-center justify-between py-2.5">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-[var(--bk-text)]">{ch.client_name}</p>
              <p className="text-xs text-[var(--bk-text-dim)]">
                {ch.barber_name} \u{2022} {ch.status}
              </p>
            </div>
            <span className="ml-2 text-sm font-bold tabular-nums text-[var(--bk-text)]">
              {formatMoney(ch.amount)}
            </span>
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
        <h1 className="bk-heading text-xl">Задачи</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={6} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">Задачи</h1>
        <p className="mt-4 text-center text-sm text-[var(--bk-red)]">{error}</p>
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
        <h1 className="bk-heading text-xl">Задачи</h1>
        {totalPending > 0 ? (
          <span className="text-sm text-[var(--bk-text-secondary)]">
            {totalPending} {totalPending === 1 ? 'задача' : 'задач'}
          </span>
        ) : (
          <span className="text-sm font-semibold text-[var(--bk-green)]">Всё выполнено</span>
        )}
      </div>
      <p className="mt-1 px-4 text-xs text-[var(--bk-text-dim)]">{tasks.date}</p>

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
