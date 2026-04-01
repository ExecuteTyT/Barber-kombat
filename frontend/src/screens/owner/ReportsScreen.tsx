import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

import { IconArrowLeft, IconChevronRight } from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useOwnerStore } from '../../stores/ownerStore'
import type { BranchRevenue, BranchClients } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function formatMoneyShort(kopecks: number): string {
  const rubles = kopecks / 100
  if (rubles >= 1_000_000) return (rubles / 1_000_000).toFixed(1) + 'M \u{20BD}'
  if (rubles >= 1_000) return (rubles / 1_000).toFixed(0) + 'k \u{20BD}'
  return rubles.toFixed(0) + ' \u{20BD}'
}

function formatMoneyAxis(kopecks: number): string {
  const rubles = kopecks / 100
  if (rubles >= 1_000_000) return (rubles / 1_000_000).toFixed(1) + 'M'
  if (rubles >= 1_000) return (rubles / 1_000).toFixed(0) + 'k'
  return String(rubles)
}

type ReportType = 'revenue' | 'day-to-day' | 'clients'

const REPORT_CARDS: { key: ReportType; label: string; desc: string }[] = [
  { key: 'revenue', label: 'Выручка по филиалам', desc: 'Дневная выручка, месяц и план' },
  { key: 'day-to-day', label: 'День за днём', desc: 'Сравнение с предыдущими месяцами' },
  { key: 'clients', label: 'Клиенты', desc: 'Удержание, средний чек, новые vs повторные' },
]

/* ---------- Stat card helper ---------- */

function StatCard({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string | number
  sub?: string
  accent?: boolean
}) {
  return (
    <div className="bk-card flex-1 p-3 text-center">
      <p className="text-[10px] leading-tight text-[var(--bk-text-secondary)]">{label}</p>
      <p
        className={`mt-0.5 text-base font-bold tabular-nums ${accent ? 'text-[var(--bk-gold)]' : 'text-[var(--bk-text)]'}`}
      >
        {value}
      </p>
      {sub && (
        <p className="mt-0.5 text-[10px] text-[var(--bk-text-dim)]">{sub}</p>
      )}
    </div>
  )
}

/* ---------- Revenue report ---------- */

function RevenueReport({ branches, networkToday, networkMtd }: {
  branches: BranchRevenue[]
  networkToday: number
  networkMtd: number
}) {
  const networkPlanTarget = branches.reduce((s, b) => s + b.plan_target, 0)
  const networkPlanPct = networkPlanTarget > 0
    ? ((networkMtd / networkPlanTarget) * 100).toFixed(0)
    : '0'

  return (
    <div>
      {/* Network summary */}
      <div className="mb-4 flex gap-3">
        <StatCard label="Сегодня (сеть)" value={formatMoney(networkToday)} />
        <StatCard label="Месяц (сеть)" value={formatMoney(networkMtd)} sub={`${networkPlanPct}% плана`} />
      </div>

      {/* Per-branch cards */}
      <div className="space-y-2">
        {branches.map((b) => (
          <div key={b.branch_id} className="bk-card p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-[var(--bk-text)]">{b.name}</span>
              <span className="text-xs text-[var(--bk-text-secondary)]">
                {b.barbers_in_shift}/{b.barbers_total} в смене
              </span>
            </div>

            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-lg font-bold tabular-nums text-[var(--bk-text)]">
                {formatMoney(b.revenue_today)}
              </span>
              <span className="text-xs text-[var(--bk-text-secondary)]">сегодня</span>
            </div>

            {/* Progress bar */}
            <div className="mt-2">
              <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
                <div
                  className="bk-progress-fill h-full transition-all duration-700"
                  style={{ width: `${Math.min(b.plan_percentage, 100)}%` }}
                />
              </div>
              <div className="mt-1 flex items-baseline justify-between text-xs">
                <span className="text-[var(--bk-text-dim)]">
                  {formatMoney(b.revenue_mtd)} / {b.plan_target > 0 ? formatMoney(b.plan_target) : 'нет плана'}
                </span>
                <span className="font-bold tabular-nums text-[var(--bk-gold)]">
                  {b.plan_percentage.toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---------- Day-to-day report ---------- */

function DayToDayChart() {
  const { dayToDay, reportsLoading, fetchDayToDay } = useOwnerStore()

  useEffect(() => {
    fetchDayToDay()
  }, [fetchDayToDay])

  if (reportsLoading && !dayToDay) {
    return <LoadingSkeleton lines={6} />
  }

  if (!dayToDay) return null

  // Build chart from all available days across all 3 months
  const allDays = new Set<number>()
  dayToDay.current_month.daily_cumulative.forEach((d) => allDays.add(d.day))
  dayToDay.prev_month.daily_cumulative.forEach((d) => allDays.add(d.day))
  dayToDay.prev_prev_month.daily_cumulative.forEach((d) => allDays.add(d.day))
  const sortedDays = Array.from(allDays).sort((a, b) => a - b)

  const chartData = sortedDays.map((day) => {
    const cur = dayToDay.current_month.daily_cumulative.find((d) => d.day === day)
    const prev = dayToDay.prev_month.daily_cumulative.find((d) => d.day === day)
    const prevPrev = dayToDay.prev_prev_month.daily_cumulative.find((d) => d.day === day)
    return {
      day,
      [dayToDay.current_month.name]: cur?.amount ?? null,
      [dayToDay.prev_month.name]: prev?.amount ?? null,
      [dayToDay.prev_prev_month.name]: prevPrev?.amount ?? null,
    }
  })

  const isPrevPositive = dayToDay.comparison.vs_prev.startsWith('+')
  const isPrevPrevPositive = dayToDay.comparison.vs_prev_prev.startsWith('+')

  return (
    <div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--bk-border)" />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11, fill: 'var(--bk-text-dim)' }}
            stroke="var(--bk-border)"
          />
          <YAxis
            tickFormatter={formatMoneyAxis}
            tick={{ fontSize: 11, fill: 'var(--bk-text-dim)' }}
            width={50}
            stroke="var(--bk-border)"
          />
          <Tooltip
            formatter={(value) => formatMoney(value as number)}
            contentStyle={{
              backgroundColor: 'var(--bk-bg-card)',
              border: '1px solid var(--bk-border-gold)',
              borderRadius: '12px',
              fontSize: 12,
              color: 'var(--bk-text)',
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: 'var(--bk-text-secondary)' }} />
          <Line
            type="monotone"
            dataKey={dayToDay.current_month.name}
            stroke="var(--bk-gold)"
            strokeWidth={2.5}
            dot={{ r: 2, fill: 'var(--bk-gold)' }}
            activeDot={{ r: 5 }}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey={dayToDay.prev_month.name}
            stroke="#3b82f6"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey={dayToDay.prev_prev_month.name}
            stroke="#a78bfa"
            strokeWidth={1.5}
            strokeDasharray="3 3"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="mt-3 flex gap-3">
        <div className="bk-card flex-1 p-3 text-center">
          <p className="text-[10px] text-[var(--bk-text-secondary)]">
            vs {dayToDay.prev_month.name}
          </p>
          <p className={`text-base font-bold ${isPrevPositive ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}`}>
            {dayToDay.comparison.vs_prev}
          </p>
        </div>
        <div className="bk-card flex-1 p-3 text-center">
          <p className="text-[10px] text-[var(--bk-text-secondary)]">
            vs {dayToDay.prev_prev_month.name}
          </p>
          <p className={`text-base font-bold ${isPrevPrevPositive ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}`}>
            {dayToDay.comparison.vs_prev_prev}
          </p>
        </div>
      </div>
    </div>
  )
}

/* ---------- Clients report ---------- */

function ClientsReport() {
  const { clients, reportsLoading, fetchClients } = useOwnerStore()

  useEffect(() => {
    fetchClients()
  }, [fetchClients])

  if (reportsLoading && !clients) {
    return <LoadingSkeleton lines={8} />
  }

  if (!clients) return null

  return (
    <div>
      {/* Network summary: 4 key metrics */}
      <div className="mb-3 grid grid-cols-2 gap-2">
        <StatCard
          label="Удержание (сеть)"
          value={`${clients.network_retention_rate}%`}
          accent
        />
        <StatCard
          label="Всего клиентов"
          value={clients.network_total_mtd}
          sub={`${clients.network_new_mtd} нов. / ${clients.network_returning_mtd} повт.`}
        />
        <StatCard
          label="Ср. чек (новые)"
          value={clients.network_avg_check_new > 0 ? formatMoneyShort(clients.network_avg_check_new) : '\u{2014}'}
        />
        <StatCard
          label="Ср. чек (повторные)"
          value={clients.network_avg_check_returning > 0 ? formatMoneyShort(clients.network_avg_check_returning) : '\u{2014}'}
        />
      </div>

      {/* Per-branch breakdown */}
      <div className="space-y-2">
        {clients.branches.map((b) => (
          <BranchClientCard key={b.branch_id} branch={b} />
        ))}
      </div>
    </div>
  )
}

function BranchClientCard({ branch: b }: { branch: BranchClients }) {
  const checkDiff = b.avg_check_returning > 0 && b.avg_check_new > 0
    ? ((b.avg_check_returning - b.avg_check_new) / b.avg_check_new * 100).toFixed(0)
    : null

  return (
    <div className="bk-card p-3">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--bk-text)]">{b.name}</span>
        <span className="rounded-full bg-[var(--bk-bg-elevated)] px-2 py-0.5 text-xs font-bold text-[var(--bk-gold)]">
          {b.retention_rate}% удерж.
        </span>
      </div>

      {/* Today's quick stats */}
      <div className="mt-2 flex items-center gap-2 text-xs text-[var(--bk-text-secondary)]">
        <span>Сегодня: {b.total_today} клиент{b.total_today === 1 ? '' : b.total_today < 5 ? 'а' : 'ов'}</span>
        <span className="text-[var(--bk-text-dim)]">|</span>
        <span>{b.new_clients_today} нов.</span>
        <span>{b.returning_clients_today} повт.</span>
      </div>

      {/* Monthly grid */}
      <div className="mt-2 grid grid-cols-4 gap-1 text-center text-xs">
        <div>
          <p className="text-[10px] text-[var(--bk-text-dim)]">Новые</p>
          <p className="font-bold text-[var(--bk-text)]">{b.new_clients_mtd}</p>
        </div>
        <div>
          <p className="text-[10px] text-[var(--bk-text-dim)]">Повторные</p>
          <p className="font-bold text-[var(--bk-text)]">{b.returning_clients_mtd}</p>
        </div>
        <div>
          <p className="text-[10px] text-[var(--bk-text-dim)]">Всего</p>
          <p className="font-bold text-[var(--bk-text)]">{b.total_mtd}</p>
        </div>
        <div>
          <p className="text-[10px] text-[var(--bk-text-dim)]">Визитов</p>
          <p className="font-bold text-[var(--bk-text)]">{b.visits_mtd}</p>
        </div>
      </div>

      {/* Average check comparison */}
      {(b.avg_check_new > 0 || b.avg_check_returning > 0) && (
        <div className="mt-2 flex items-center justify-between rounded-lg bg-[var(--bk-bg-elevated)] px-2.5 py-1.5 text-xs">
          <div>
            <span className="text-[var(--bk-text-dim)]">Ср. чек: </span>
            <span className="font-semibold text-[var(--bk-text)]">
              {b.avg_check_new > 0 ? formatMoneyShort(b.avg_check_new) : '\u{2014}'} нов.
            </span>
            <span className="mx-1 text-[var(--bk-text-dim)]">/</span>
            <span className="font-semibold text-[var(--bk-text)]">
              {b.avg_check_returning > 0 ? formatMoneyShort(b.avg_check_returning) : '\u{2014}'} повт.
            </span>
          </div>
          {checkDiff && (
            <span className={`font-bold ${Number(checkDiff) >= 0 ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}`}>
              {Number(checkDiff) >= 0 ? '+' : ''}{checkDiff}%
            </span>
          )}
        </div>
      )}
    </div>
  )
}

/* ---------- Main screen ---------- */

export default function ReportsScreen() {
  const [activeReport, setActiveReport] = useState<ReportType | null>(null)
  const { revenue, fetchDashboard } = useOwnerStore()

  useEffect(() => {
    if (!revenue) fetchDashboard()
  }, [revenue, fetchDashboard])

  if (!activeReport) {
    return (
      <div className="pb-4 pt-4">
        <h1 className="bk-heading px-4 text-xl">Отчёты</h1>
        <div className="mx-4 mt-4 space-y-2">
          {REPORT_CARDS.map((r, i) => (
            <button
              key={r.key}
              type="button"
              className="bk-card bk-fade-up flex w-full items-center justify-between p-4 text-left transition-all active:scale-[0.98]"
              style={{ animationDelay: `${i * 60}ms` }}
              onClick={() => setActiveReport(r.key)}
            >
              <div>
                <p className="font-medium text-[var(--bk-text)]">{r.label}</p>
                <p className="mt-0.5 text-sm text-[var(--bk-text-secondary)]">{r.desc}</p>
              </div>
              <IconChevronRight size={18} className="text-[var(--bk-text-dim)]" />
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      <div className="flex items-center gap-2 px-4">
        <button
          type="button"
          className="flex items-center gap-1 text-sm text-[var(--bk-gold)]"
          onClick={() => setActiveReport(null)}
        >
          <IconArrowLeft size={18} />
          Назад
        </button>
        <h1 className="bk-heading text-lg">
          {REPORT_CARDS.find((r) => r.key === activeReport)?.label}
        </h1>
      </div>

      <div className="mx-4 mt-4">
        {activeReport === 'revenue' &&
          (revenue ? (
            <RevenueReport
              branches={revenue.branches}
              networkToday={revenue.network_total_today}
              networkMtd={revenue.network_total_mtd}
            />
          ) : (
            <LoadingSkeleton lines={6} />
          ))}

        {activeReport === 'day-to-day' && <DayToDayChart />}

        {activeReport === 'clients' && <ClientsReport />}
      </div>
    </div>
  )
}
