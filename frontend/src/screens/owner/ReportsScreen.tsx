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

// --- Revenue table ---
function RevenueTable({ branches }: { branches: BranchRevenue[] }) {
  return (
    <div className="space-y-2">
      {branches.map((b) => (
        <div key={b.branch_id} className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-3">
          <div className="flex items-baseline justify-between">
            <span className="font-medium">{b.name}</span>
            <span className="font-bold tabular-nums">{formatMoney(b.revenue_today)}</span>
          </div>
          <div className="mt-1 flex items-baseline justify-between text-xs text-[var(--tg-theme-hint-color)]">
            <span>Месяц: {formatMoney(b.revenue_mtd)}</span>
            <span>{b.plan_percentage.toFixed(0)}% плана</span>
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Day-to-day chart ---
function DayToDayChart() {
  const { dayToDay, reportsLoading, fetchDayToDay } = useOwnerStore()

  useEffect(() => {
    fetchDayToDay()
  }, [fetchDayToDay])

  if (reportsLoading && !dayToDay) {
    return <LoadingSkeleton lines={6} />
  }

  if (!dayToDay) return null

  // Merge 3 months into chart data
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
          <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
          <XAxis dataKey="day" tick={{ fontSize: 11 }} />
          <YAxis tickFormatter={formatMoneyAxis} tick={{ fontSize: 11 }} width={50} />
          <Tooltip
            formatter={(value: number) => formatMoney(value)}
            contentStyle={{
              backgroundColor: 'var(--tg-theme-bg-color)',
              border: '1px solid var(--tg-theme-hint-color)',
              borderRadius: '8px',
              fontSize: 12,
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey={dayToDay.current_month.name}
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
          />
          <Line
            type="monotone"
            dataKey={dayToDay.prev_month.name}
            stroke="#a855f7"
            strokeWidth={1.5}
            strokeDasharray="4 4"
            dot={false}
          />
          <Line
            type="monotone"
            dataKey={dayToDay.prev_prev_month.name}
            stroke="#6b7280"
            strokeWidth={1}
            strokeDasharray="2 2"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Comparison */}
      <div className="mt-3 flex gap-3">
        <div className="flex-1 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-2 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">vs прошлый</p>
          <p className="font-bold">{dayToDay.comparison.vs_prev}</p>
        </div>
        <div className="flex-1 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-2 text-center">
          <p className="text-xs text-[var(--tg-theme-hint-color)]">vs позапрошлый</p>
          <p className="font-bold">{dayToDay.comparison.vs_prev_prev}</p>
        </div>
      </div>
    </div>
  )
}

// --- Clients table ---
function ClientsTable({ branches }: { branches: BranchClients[] }) {
  return (
    <div className="space-y-2">
      {branches.map((b) => (
        <div key={b.branch_id} className="rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-3">
          <span className="font-medium">{b.name}</span>
          <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            <div>
              <p className="text-[var(--tg-theme-hint-color)]">Новые</p>
              <p className="font-bold">{b.new_clients_mtd}</p>
            </div>
            <div>
              <p className="text-[var(--tg-theme-hint-color)]">Повторные</p>
              <p className="font-bold">{b.returning_clients_mtd}</p>
            </div>
            <div>
              <p className="text-[var(--tg-theme-hint-color)]">Всего</p>
              <p className="font-bold">{b.total_mtd}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function ReportsScreen() {
  const [activeReport, setActiveReport] = useState<ReportType | null>(null)
  const {
    revenue,
    clients,
    reportsLoading,
    fetchDashboard,
    fetchClients,
  } = useOwnerStore()

  // Load revenue if not loaded (shared with dashboard)
  useEffect(() => {
    if (!revenue) fetchDashboard()
  }, [revenue, fetchDashboard])

  // Back to list
  if (!activeReport) {
    return (
      <div className="pb-4 pt-4">
        <h1 className="px-4 text-lg font-bold">Отчёты</h1>
        <div className="mx-4 mt-4 space-y-2">
          {REPORT_CARDS.map((r) => (
            <button
              key={r.key}
              type="button"
              className="w-full rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4 text-left active:opacity-80"
              onClick={() => {
                setActiveReport(r.key)
                if (r.key === 'clients') fetchClients()
              }}
            >
              <p className="font-medium">{r.label}</p>
              <p className="mt-0.5 text-sm text-[var(--tg-theme-hint-color)]">{r.desc}</p>
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      {/* Back button */}
      <div className="flex items-center gap-2 px-4">
        <button
          type="button"
          className="text-[var(--tg-theme-button-color)]"
          onClick={() => setActiveReport(null)}
        >
          {'\u{2190}'} Назад
        </button>
        <h1 className="text-lg font-bold">
          {REPORT_CARDS.find((r) => r.key === activeReport)?.label}
        </h1>
      </div>

      <div className="mx-4 mt-4">
        {activeReport === 'revenue' && (
          revenue ? (
            <RevenueTable branches={revenue.branches} />
          ) : (
            <LoadingSkeleton lines={6} />
          )
        )}

        {activeReport === 'day-to-day' && <DayToDayChart />}

        {activeReport === 'clients' && (
          reportsLoading && !clients ? (
            <LoadingSkeleton lines={6} />
          ) : clients ? (
            <>
              <div className="mb-3 flex gap-3">
                <div className="flex-1 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-2 text-center">
                  <p className="text-xs text-[var(--tg-theme-hint-color)]">Новые</p>
                  <p className="font-bold">{clients.network_new_mtd}</p>
                </div>
                <div className="flex-1 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-2 text-center">
                  <p className="text-xs text-[var(--tg-theme-hint-color)]">Повторные</p>
                  <p className="font-bold">{clients.network_returning_mtd}</p>
                </div>
                <div className="flex-1 rounded-lg bg-[var(--tg-theme-secondary-bg-color)] p-2 text-center">
                  <p className="text-xs text-[var(--tg-theme-hint-color)]">Всего</p>
                  <p className="font-bold">{clients.network_total_mtd}</p>
                </div>
              </div>
              <ClientsTable branches={clients.branches} />
            </>
          ) : null
        )}
      </div>
    </div>
  )
}
