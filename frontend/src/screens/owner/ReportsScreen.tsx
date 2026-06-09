import { useEffect, useState } from 'react'
import {
  Area,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

import { IconArrowLeft, IconArrowRight, IconChevronRight } from '../../components/Icons'
import InfoTip from '../../components/InfoTip'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useOwnerStore } from '../../stores/ownerStore'
import type { BranchRevenue, BranchClients } from '../../types'

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

function shiftIso(iso: string, deltaDays: number): string {
  const d = new Date(iso + 'T00:00:00')
  d.setDate(d.getDate() + deltaDays)
  return d.toISOString().slice(0, 10)
}

function formatHumanDate(iso: string): string {
  return new Date(iso + 'T00:00:00').toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

const RU_MONTHS_NOM = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

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
  { key: 'revenue', label: 'Выручка по филиалам', desc: 'За любой день — архив с начала работы' },
  { key: 'day-to-day', label: 'День за днём', desc: 'Сравнение с предыдущими месяцами' },
  { key: 'clients', label: 'Клиенты', desc: 'Доля повторных, средний чек, новые vs повторные' },
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

/* ---------- Revenue report (historical, per-date) ---------- */

function DatePickerBar({
  value,
  onChange,
}: {
  value: string
  onChange: (iso: string) => void
}) {
  const today = todayIso()
  const isToday = value === today
  const canGoForward = value < today

  const go = (delta: number) => (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    onChange(shiftIso(value, delta))
  }

  return (
    <div className="mb-3 flex items-center gap-2">
      <button
        type="button"
        className="rounded-lg bg-[var(--bk-bg-elevated)] p-2 text-[var(--bk-gold)] active:opacity-70"
        onClick={go(-1)}
        aria-label="Предыдущий день"
      >
        <IconArrowLeft size={16} className="pointer-events-none" />
      </button>
      <input
        type="date"
        className="flex-1 rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-2 py-1.5 text-sm text-[var(--bk-text)]"
        value={value}
        max={today}
        onChange={(e) => e.target.value && onChange(e.target.value)}
      />
      <button
        type="button"
        className="rounded-lg bg-[var(--bk-bg-elevated)] p-2 text-[var(--bk-gold)] disabled:opacity-30"
        disabled={!canGoForward}
        onClick={go(1)}
        aria-label="Следующий день"
      >
        <IconArrowRight size={16} className="pointer-events-none" />
      </button>
      {!isToday && (
        <button
          type="button"
          className="rounded-lg bg-[var(--bk-gold)] px-2.5 py-1.5 text-xs font-semibold text-[var(--bk-bg-primary)]"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onChange(today)
          }}
        >
          Сегодня
        </button>
      )}
    </div>
  )
}

function RevenueReport() {
  const revenueByDate = useOwnerStore((s) => s.revenueByDate)
  const revenueByDateLoading = useOwnerStore((s) => s.revenueByDateLoading)
  const fetchRevenueByDate = useOwnerStore((s) => s.fetchRevenueByDate)
  const [dateIso, setDateIso] = useState<string>(todayIso())

  useEffect(() => {
    fetchRevenueByDate(dateIso)
  }, [dateIso, fetchRevenueByDate])

  const isToday = dateIso === todayIso()

  return (
    <div>
      <DatePickerBar value={dateIso} onChange={setDateIso} />

      {revenueByDateLoading && !revenueByDate && <LoadingSkeleton lines={6} />}

      {revenueByDate && (
        <RevenueForDate
          report={revenueByDate}
          dateIso={dateIso}
          isToday={isToday}
        />
      )}
    </div>
  )
}

function RevenueForDate({
  report,
  dateIso,
  isToday,
}: {
  report: { branches: BranchRevenue[]; network_total_today: number; network_total_mtd: number }
  dateIso: string
  isToday: boolean
}) {
  const { branches, network_total_today: networkDay, network_total_mtd: networkMtd } = report
  const networkPlanTarget = branches.reduce((s, b) => s + b.plan_target, 0)
  const networkPlanPct =
    networkPlanTarget > 0 ? ((networkMtd / networkPlanTarget) * 100).toFixed(0) : '0'

  const d = new Date(dateIso + 'T00:00:00')
  const monthNom = RU_MONTHS_NOM[d.getMonth()]
  const dayNum = d.getDate()

  const dayLabel = isToday ? 'Сегодня' : formatHumanDate(dateIso)
  // Days 1-N of the current month. Simpler and less ambiguous than "С начала..."
  const mtdLabel = `${monthNom} 1–${dayNum}`
  const mtdHint = 'накопительная сеть с 1-го по выбранный день'

  return (
    <>
      <div className="mb-1 flex gap-3">
        <StatCard label={dayLabel} value={formatMoney(networkDay)} />
        <StatCard label={mtdLabel} value={formatMoney(networkMtd)} sub={`${networkPlanPct}% плана`} />
      </div>
      <p className="mb-3 px-1 text-[10px] text-[var(--bk-text-dim)]">{mtdHint}</p>

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
              <span className="text-xs text-[var(--bk-text-secondary)]">
                {isToday ? 'сегодня' : 'за день'}
              </span>
            </div>

            <div className="mt-2">
              <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
                <div
                  className="bk-progress-fill h-full transition-all duration-700"
                  style={{ width: `${Math.min(b.plan_percentage, 100)}%` }}
                />
              </div>
              <div className="mt-1 flex items-baseline justify-between text-xs">
                <span className="text-[var(--bk-text-dim)]">
                  {formatMoney(b.revenue_mtd)} /{' '}
                  {b.plan_target > 0 ? formatMoney(b.plan_target) : 'нет плана'}
                </span>
                <span className="font-bold tabular-nums text-[var(--bk-gold)]">
                  {b.plan_percentage.toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        ))}
        {branches.length === 0 && (
          <p className="py-4 text-center text-sm text-[var(--bk-text-secondary)]">
            Нет данных за эту дату
          </p>
        )}
      </div>
    </>
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

  const cur = dayToDay.current_month
  const prev = dayToDay.prev_month
  const prevPrev = dayToDay.prev_prev_month

  // Build chart from all available days across all 3 months.
  const allDays = new Set<number>()
  cur.daily_cumulative.forEach((d) => allDays.add(d.day))
  prev.daily_cumulative.forEach((d) => allDays.add(d.day))
  prevPrev.daily_cumulative.forEach((d) => allDays.add(d.day))
  const sortedDays = Array.from(allDays).sort((a, b) => a - b)

  const chartData = sortedDays.map((day) => ({
    day,
    [cur.name]: cur.daily_cumulative.find((d) => d.day === day)?.amount ?? null,
    [prev.name]: prev.daily_cumulative.find((d) => d.day === day)?.amount ?? null,
    [prevPrev.name]: prevPrev.daily_cumulative.find((d) => d.day === day)?.amount ?? null,
  }))

  // Same-period totals: cumulative up to the current month's last filled day.
  const curMaxDay = cur.daily_cumulative.reduce((m, d) => Math.max(m, d.day), 0)
  const cumAt = (arr: { day: number; amount: number }[]) =>
    arr.filter((d) => d.day <= curMaxDay).reduce((v, d) => Math.max(v, d.amount), 0)
  const curTotal = cumAt(cur.daily_cumulative)
  const prevTotal = cumAt(prev.daily_cumulative)
  const prevPrevTotal = cumAt(prevPrev.daily_cumulative)

  const isPrevPositive = dayToDay.comparison.vs_prev.startsWith('+')
  const isPrevPrevPositive = dayToDay.comparison.vs_prev_prev.startsWith('+')

  return (
    <div>
      {/* Headline: current pace + same-period deltas */}
      <div className="bk-card mb-3 p-3">
        <p className="flex items-center text-[11px] text-[var(--bk-text-secondary)]">
          {cur.name} — выручка за 1–{curMaxDay}
          <InfoTip text="Накопленная выручка с 1-го числа месяца. Сравниваем темп за одинаковый период (одинаковое число дней) с прошлыми месяцами." />
        </p>
        <p
          className="text-2xl font-bold tabular-nums text-[var(--bk-gold)]"
          style={{ fontFamily: 'var(--bk-font-heading)' }}
        >
          {formatMoney(curTotal)}
        </p>
        <div className="mt-1 flex gap-3 text-xs">
          <span className={isPrevPositive ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}>
            {isPrevPositive ? '▲' : '▼'} {dayToDay.comparison.vs_prev} к {prev.name}
          </span>
          <span className={isPrevPrevPositive ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}>
            {isPrevPrevPositive ? '▲' : '▼'} {dayToDay.comparison.vs_prev_prev} к {prevPrev.name}
          </span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="curFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--bk-gold)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="var(--bk-gold)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--bk-border)" vertical={false} />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 11, fill: 'var(--bk-text-dim)' }}
            stroke="var(--bk-border)"
            interval="preserveStartEnd"
            minTickGap={18}
          />
          <YAxis
            tickFormatter={formatMoneyAxis}
            tick={{ fontSize: 11, fill: 'var(--bk-text-dim)' }}
            width={42}
            stroke="var(--bk-border)"
          />
          <Tooltip
            labelFormatter={(d) => `День ${d}`}
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
          <Area
            type="monotone"
            dataKey={cur.name}
            stroke="var(--bk-gold)"
            strokeWidth={3}
            fill="url(#curFill)"
            dot={false}
            activeDot={{ r: 5 }}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey={prev.name}
            stroke="#3b82f6"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            dataKey={prevPrev.name}
            stroke="#a78bfa"
            strokeWidth={1.5}
            strokeDasharray="3 3"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Same-period totals fill the space with concrete numbers */}
      <p className="mb-2 mt-3 px-1 text-[10px] text-[var(--bk-text-dim)]">
        Итого за одинаковый период (1–{curMaxDay}):
      </p>
      <div className="flex gap-2">
        <StatCard label={cur.name} value={formatMoneyShort(curTotal)} accent />
        <StatCard label={prev.name} value={formatMoneyShort(prevTotal)} />
        <StatCard label={prevPrev.name} value={formatMoneyShort(prevPrevTotal)} />
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
          label="Повторные % (сеть)"
          value={`${clients.network_retention_rate}%`}
          sub="доля тех, кто уже бывал раньше"
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
          {b.retention_rate}% повт.
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
        {activeReport === 'revenue' && <RevenueReport />}

        {activeReport === 'day-to-day' && <DayToDayChart />}

        {activeReport === 'clients' && <ClientsReport />}
      </div>
    </div>
  )
}
