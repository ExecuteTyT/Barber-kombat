import { useEffect } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAdminStore } from '../../stores/adminStore'

const MEDALS = ['🥇', '🥈', '🥉']

export default function AdminKpiScreen() {
  const { networkKpi, loading, error, fetchNetworkKpi } = useAdminStore()

  useEffect(() => {
    fetchNetworkKpi()
  }, [fetchNetworkKpi])

  if (loading && !networkKpi) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">KPI администраторов</h1>
        <div className="mt-4">
          <LoadingSkeleton lines={4} />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 pb-4 pt-4">
        <h1 className="bk-heading text-xl">KPI администраторов</h1>
        <p className="mt-4 text-center text-sm text-[var(--bk-red)]">{error}</p>
      </div>
    )
  }

  if (!networkKpi) return null

  return (
    <div className="px-4 pb-4 pt-4">
      <h1 className="bk-heading text-xl">KPI администраторов</h1>
      <p className="mt-0.5 text-xs text-[var(--bk-text-secondary)]">
        Рейтинг филиалов {'•'} {networkKpi.month}
      </p>

      {networkKpi.branches.length === 0 ? (
        <p className="mt-8 text-center text-sm text-[var(--bk-text-secondary)]">
          Нет данных за этот месяц
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          {networkKpi.branches.map((b) => (
            <div key={b.branch_id} className="bk-card p-4">
              <div className="flex items-center gap-3">
                <div className="w-7 text-center text-lg">
                  {b.rank != null && b.rank <= 3 ? MEDALS[b.rank - 1] : `#${b.rank ?? '—'}`}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-[var(--bk-text)]">{b.branch_name}</p>
                  <p className="text-xs text-[var(--bk-text-dim)]">{b.survey_count} опросов</p>
                </div>
                <p
                  className="text-2xl font-bold tabular-nums text-[var(--bk-gold)]"
                  style={{ fontFamily: 'var(--bk-font-heading)' }}
                >
                  {b.composite_score ?? '—'}
                </p>
              </div>
              <div className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
                <Stat label="Админ" value={b.admin_avg != null ? `${b.admin_avg}` : '—'} />
                <Stat label="Подтв." value={`${b.confirmation_rate}%`} />
                <Stat label="NPS" value={b.nps != null ? `${b.nps}%` : '—'} />
                <Stat label="Негатив" value={`${b.negatives}`} danger={b.negatives > 0} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div>
      <p
        className={`font-semibold tabular-nums ${danger ? 'text-[var(--bk-red)]' : 'text-[var(--bk-text)]'}`}
      >
        {value}
      </p>
      <p className="text-[var(--bk-text-dim)]">{label}</p>
    </div>
  )
}
