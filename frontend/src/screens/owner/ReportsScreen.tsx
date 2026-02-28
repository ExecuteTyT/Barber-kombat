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

function formatMoneyAxis(kopecks: number): string {
  const rubles = kopecks / 100
  if (rubles >= 1_000_000) return (rubles / 1_000_000).toFixed(1) + 'M'
  if (rubles >= 1_000) return (rubles / 1_000).toFixed(0) + 'k'
  return String(rubles)
}

type ReportType = 'revenue' | 'day-to-day' | 'clients'

const REPORT_CARDS: { key: ReportType; label: string; desc: string }[] = [
  { key: 'revenue', label: 'Выручка по филиалам', desc: 'Дневная и месячная выручка' },
  { key: 'day-to-day', label: 'Day-to-day', desc: 'Сравнение с предыдущими месяцами' },
  { key: 'clients', label: 'Клиенты', desc: 'Новые и повторные клиенты' },
]

function RevenueTable({ branches }: { branches: BranchRevenue[] }) {
  return (
    <div className="space-y-2">
      {branches.map((b) => (
        <div key={b.branch_id} className="bk-card p-3">
          <div className="flex items-baseline justify-between">
            <span className="font-medium text-[var(--bk-text)]">{b.name}</span>
            <span className="font-bold tabular-nums text-[var(--bk-text)]">
              {formatMoney(b.revenue_today)}
            </span>
          </div>
          <div className="mt-1 flex items-baseline justify-between text-xs text-[var(--bk-text-secondary)]">
            <span>Месяц: {formatMoney(b.revenue_mtd)}</span>
            <span className="font-semibold text-[var(--bk-gold)]">
              {b.plan_percentage.toFixed(0)}% плана
            </span>
          </div>
        </div>
      ))}
    </div>
  )
}

function DayToDayChart() {
  const { dayToDay, reportsLoading, fetchDayToDay } = useOwnerStore()

  useEffect(() => {
    fetchDayToDay()
  }, [fetchDayToDay])

  if (reportsLoading && !dayToDay) {
    return <LoadingSkeleton lines={6} />
  }

  if (!dayToDay) return null

  const chartData = dayToDay.current_month.daily_cumulative.map((p) => {
    const prev = dayToDay.prev_month.daily_cumulative.find((d) => d.day === p.day)
    const prevPrev = dayToDay.prev_prev_month.daily_cumulative.find((d) => d.day === p.day)
    return {
      day: p.day,
      [dayToDay.current_month.name]: p.amount,
      [dayToDay.prev_month.name]: prev?.amount ?? null,
      [dayToDay.prev_prev_month.name]: prevPrev?.amount ?? null,
    }
  })

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
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey={dayToDay.prev_month.name}
            stroke="var(--bk-score-cs)"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false}
          />
          <Line
            type="monotone"
            dataKey={dayToDay.prev_prev_month.name}
            stroke="var(--bk-text-dim)"
            strokeWidth={1}
            strokeDasharray="2 2"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>

      <div className="mt-3 flex gap-3">
        <div className="bk-card flex-1 p-3 text-center">
          <p className="text-xs text-[var(--bk-text-secondary)]">vs прошлый</p>
          <p className="font-bold text-[var(--bk-text)]">{dayToDay.comparison.vs_prev}</p>
        </div>
        <div className="bk-card flex-1 p-3 text-center">
          <p className="text-xs text-[var(--bk-text-secondary)]">vs позапрошлый</p>
          <p className="font-bold text-[var(--bk-text)]">{dayToDay.comparison.vs_prev_prev}</p>
        </div>
      </div>
    </div>
  )
}

function ClientsTable({ branches }: { branches: BranchClients[] }) {
  return (
    <div className="space-y-2">
      {branches.map((b) => (
        <div key={b.branch_id} className="bk-card p-3">
          <span className="font-medium text-[var(--bk-text)]">{b.name}</span>
          <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            <div>
              <p className="text-[var(--bk-text-secondary)]">Новые</p>
              <p className="font-bold text-[var(--bk-text)]">{b.new_clients_mtd}</p>
            </div>
            <div>
              <p className="text-[var(--bk-text-secondary)]">Повторные</p>
              <p className="font-bold text-[var(--bk-text)]">{b.returning_clients_mtd}</p>
            </div>
            <div>
              <p className="text-[var(--bk-text-secondary)]">Всего</p>
              <p className="font-bold text-[var(--bk-text)]">{b.total_mtd}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ReportsScreen() {
  const [activeReport, setActiveReport] = useState<ReportType | null>(null)
  const { revenue, clients, reportsLoading, fetchDashboard, fetchClients } = useOwnerStore()

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
              onClick={() => {
                setActiveReport(r.key)
                if (r.key === 'clients') fetchClients()
              }}
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
          (revenue ? <RevenueTable branches={revenue.branches} /> : <LoadingSkeleton lines={6} />)}

        {activeReport === 'day-to-day' && <DayToDayChart />}

        {activeReport === 'clients' &&
          (reportsLoading && !clients ? (
            <LoadingSkeleton lines={6} />
          ) : clients ? (
            <>
              <div className="mb-3 flex gap-3">
                {[
                  { label: 'Новые', value: clients.network_new_mtd },
                  { label: 'Повторные', value: clients.network_returning_mtd },
                  { label: 'Всего', value: clients.network_total_mtd },
                ].map((s) => (
                  <div key={s.label} className="bk-card flex-1 p-3 text-center">
                    <p className="text-xs text-[var(--bk-text-secondary)]">{s.label}</p>
                    <p className="font-bold text-[var(--bk-text)]">{s.value}</p>
                  </div>
                ))}
              </div>
              <ClientsTable branches={clients.branches} />
            </>
          ) : null)}
      </div>
    </div>
  )
}
