import { useEffect } from 'react'

import { IconCheckCircle, IconMessageCircle, IconPhone } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { telLink, waLink } from '../../lib/contact'
import { useAdminStore } from '../../stores/adminStore'
import { useAuthStore } from '../../stores/authStore'

const CONFIRM_TEXT = 'Здравствуйте! Подтверждаете запись в барбершоп MAKON? Будем рады видеть вас.'
const QC_TEXT =
  'Здравствуйте! Это барбершоп MAKON. Хотим узнать, всё ли вам понравилось в прошлый визит?'

export default function CallsScreen() {
  const { user } = useAuthStore()
  const { calls, qcCalls, loading, error, fetchCalls, markCall, fetchQcCalls, markQcCall } =
    useAdminStore()

  useEffect(() => {
    if (user?.branch_id) {
      fetchCalls(user.branch_id)
      fetchQcCalls(user.branch_id)
    }
  }, [user?.branch_id, fetchCalls, fetchQcCalls])

  if (loading && !calls) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">Звонки</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={5} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">Звонки</h1>
        <p className="mt-4 text-center text-sm text-[var(--bk-red)]">{error}</p>
      </div>
    )
  }

  if (!calls) return null

  const hasQc = qcCalls && qcCalls.total > 0

  return (
    <div className="px-4 pb-4 pt-4">
      <h1 className="bk-heading text-xl">Звонки</h1>
      <p className="mt-0.5 text-xs text-[var(--bk-text-secondary)]">
        Подтверждение ближайших записей
      </p>

      {/* Summary */}
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="bk-card p-3">
          <p className="text-xs text-[var(--bk-text-secondary)]">Подтверждено</p>
          <p
            className="text-2xl font-bold tabular-nums"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {calls.confirmation_rate}%
          </p>
          <p className="text-xs text-[var(--bk-text-dim)]">
            {calls.confirmed_upcoming} из {calls.total_upcoming} записей
          </p>
        </div>
        <div className="bk-card p-3">
          <p className="text-xs text-[var(--bk-text-secondary)]">Обзвон сегодня</p>
          <p
            className="text-2xl font-bold tabular-nums"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {calls.call_progress}%
          </p>
          <p className="text-xs text-[var(--bk-text-dim)]">
            {calls.called_count} из {calls.to_call_count} обзвонено
          </p>
        </div>
      </div>

      {/* To-call list */}
      {calls.to_call.length === 0 ? (
        <div className="mt-8 flex flex-col items-center text-center">
          <IconCheckCircle size={40} className="text-[var(--bk-green)]" />
          <p className="mt-2 text-sm text-[var(--bk-text-secondary)]">
            Все ближайшие записи подтверждены
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          {calls.to_call.map((t) => (
            <div key={t.record_id} className={`bk-card p-3 ${t.called ? 'opacity-60' : ''}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-[var(--bk-text)]">
                    {t.client_name}
                  </p>
                  <p className="text-xs text-[var(--bk-text-dim)]">
                    {t.date} {'•'} {t.barber_name}
                  </p>
                </div>
                {t.called && (
                  <span className="flex items-center gap-1 text-xs text-[var(--bk-green)]">
                    <IconCheckCircle size={14} /> Обзвонен
                  </span>
                )}
              </div>

              {t.phone && (
                <div className="mt-2 flex gap-2">
                  <a
                    href={waLink(t.phone, CONFIRM_TEXT) ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl bg-[var(--bk-green)] text-sm font-semibold text-white"
                  >
                    <IconMessageCircle size={16} /> WhatsApp
                  </a>
                  <a
                    href={telLink(t.phone) ?? undefined}
                    className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl bg-[var(--bk-bg-elevated)] text-sm font-semibold text-[var(--bk-text)]"
                  >
                    <IconPhone size={16} /> Позвонить
                  </a>
                </div>
              )}

              {!t.called && (
                <button
                  type="button"
                  onClick={() => user?.branch_id && markCall(user.branch_id, t.yclients_record_id)}
                  className="mt-2 min-h-[44px] w-full rounded-xl border border-[var(--bk-border-gold)] text-sm font-semibold text-[var(--bk-gold)]"
                >
                  Отметить «позвонил»
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* DataHeroes quality-control calls */}
      {hasQc && (
        <div className="mt-8">
          <h2 className="bk-heading text-lg">Контроль качества</h2>
          <p className="mt-0.5 text-xs text-[var(--bk-text-secondary)]">
            Обзвон клиентов после визита (DataHeroes)
          </p>

          <div className="mt-3 bk-card p-3">
            <p className="text-xs text-[var(--bk-text-secondary)]">Обработано</p>
            <p
              className="text-2xl font-bold tabular-nums"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {qcCalls.progress}%
            </p>
            <p className="text-xs text-[var(--bk-text-dim)]">
              {qcCalls.contacted_count} из {qcCalls.total} обработано
            </p>
          </div>

          <div className="mt-4 space-y-3">
            {qcCalls.tasks.map((t) => {
              const done = t.status === 'contacted'
              return (
                <div key={t.task_id} className={`bk-card p-3 ${done ? 'opacity-60' : ''}`}>
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-[var(--bk-text)]">
                        {t.client_name}
                      </p>
                      {t.reason && (
                        <p className="truncate text-xs text-[var(--bk-text-dim)]">
                          {t.reason}
                          {t.visit_count != null ? ` • ${t.visit_count} визит(ов)` : ''}
                        </p>
                      )}
                    </div>
                    {done && (
                      <span className="flex items-center gap-1 text-xs text-[var(--bk-green)]">
                        <IconCheckCircle size={14} /> Связался
                      </span>
                    )}
                  </div>

                  {t.phone && (
                    <div className="mt-2 flex gap-2">
                      <a
                        href={waLink(t.phone, QC_TEXT) ?? undefined}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl bg-[var(--bk-green)] text-sm font-semibold text-white"
                      >
                        <IconMessageCircle size={16} /> WhatsApp
                      </a>
                      <a
                        href={telLink(t.phone) ?? undefined}
                        className="flex min-h-[44px] flex-1 items-center justify-center gap-1.5 rounded-xl bg-[var(--bk-bg-elevated)] text-sm font-semibold text-[var(--bk-text)]"
                      >
                        <IconPhone size={16} /> Позвонить
                      </a>
                    </div>
                  )}

                  {!done && (
                    <button
                      type="button"
                      onClick={() => user?.branch_id && markQcCall(user.branch_id, t.task_id)}
                      className="mt-2 min-h-[44px] w-full rounded-xl border border-[var(--bk-border-gold)] text-sm font-semibold text-[var(--bk-gold)]"
                    >
                      Отметить «связался»
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
