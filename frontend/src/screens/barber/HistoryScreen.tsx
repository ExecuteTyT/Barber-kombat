import { useState, useEffect, useMemo } from 'react'

import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useAuthStore } from '../../stores/authStore'
import { useKombatStore } from '../../stores/kombatStore'
import type { DailyScoreEntry } from '../../types'

const WEEKDAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] as const

function formatMonthYear(year: number, month: number): string {
  const d = new Date(year, month - 1)
  const str = d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
  return str.charAt(0).toUpperCase() + str.slice(1)
}

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function getRankColor(rank: number): string {
  switch (rank) {
    case 1: return 'bg-amber-400 text-amber-950'
    case 2: return 'bg-gray-300 text-gray-800'
    case 3: return 'bg-amber-700 text-amber-100'
    default: return 'bg-[var(--tg-theme-secondary-bg-color)] text-[var(--tg-theme-hint-color)]'
  }
}

function getRankMedal(rank: number): string {
  switch (rank) {
    case 1: return '\u{1F947}'
    case 2: return '\u{1F948}'
    case 3: return '\u{1F949}'
    default: return ''
  }
}

// Build calendar grid for a given month
function buildCalendarGrid(year: number, month: number): (number | null)[][] {
  const firstDay = new Date(year, month - 1, 1)
  // JS: 0=Sun ... 6=Sat -> convert to Mon=0
  let startDow = firstDay.getDay() - 1
  if (startDow < 0) startDow = 6
  const daysInMonth = new Date(year, month, 0).getDate()

  const weeks: (number | null)[][] = []
  let week: (number | null)[] = Array.from({ length: startDow }, () => null)

  for (let day = 1; day <= daysInMonth; day++) {
    week.push(day)
    if (week.length === 7) {
      weeks.push(week)
      week = []
    }
  }
  if (week.length > 0) {
    while (week.length < 7) week.push(null)
    weeks.push(week)
  }

  return weeks
}

// Day detail popup
function DayDetail({ entry, onClose }: { entry: DailyScoreEntry; onClose: () => void }) {
  const d = new Date(entry.date + 'T00:00:00')
  const label = d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    weekday: 'short',
  })

  return (
    <div className="mx-4 mt-2 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium">{label}</span>
        <button
          type="button"
          className="text-[var(--tg-theme-hint-color)]"
          onClick={onClose}
        >
          \u{2715}
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <div>
          <span className="text-[var(--tg-theme-hint-color)]">Место</span>
          <p className="text-lg font-bold">
            {getRankMedal(entry.rank) || entry.rank}
            {entry.rank <= 3 ? '' : `-е`}
          </p>
        </div>
        <div>
          <span className="text-[var(--tg-theme-hint-color)]">Рейтинг</span>
          <p className="text-lg font-bold tabular-nums">{entry.score.toFixed(1)}</p>
        </div>
      </div>
    </div>
  )
}

// Calendar grid
function Calendar({
  year,
  month,
  scores,
}: {
  year: number
  month: number
  scores: DailyScoreEntry[]
}) {
  const [selectedDay, setSelectedDay] = useState<number | null>(null)

  const scoreMap = useMemo(() => {
    const map = new Map<number, DailyScoreEntry>()
    for (const s of scores) {
      const d = new Date(s.date + 'T00:00:00')
      if (d.getFullYear() === year && d.getMonth() + 1 === month) {
        map.set(d.getDate(), s)
      }
    }
    return map
  }, [scores, year, month])

  const weeks = useMemo(() => buildCalendarGrid(year, month), [year, month])
  const selectedEntry = selectedDay !== null ? scoreMap.get(selectedDay) : undefined

  return (
    <div>
      {/* Weekday headers */}
      <div className="grid grid-cols-7 px-4">
        {WEEKDAY_LABELS.map((d) => (
          <div key={d} className="py-1 text-center text-xs text-[var(--tg-theme-hint-color)]">
            {d}
          </div>
        ))}
      </div>

      {/* Day cells */}
      {weeks.map((week, wi) => (
        <div key={wi} className="grid grid-cols-7 px-4">
          {week.map((day, di) => {
            if (day === null) {
              return <div key={di} className="py-1.5" />
            }

            const entry = scoreMap.get(day)
            const isSelected = selectedDay === day

            return (
              <button
                key={di}
                type="button"
                className={`mx-auto my-0.5 flex h-9 w-9 items-center justify-center rounded-full text-sm font-medium transition-colors ${
                  entry
                    ? `${getRankColor(entry.rank)} ${isSelected ? 'ring-2 ring-[var(--tg-theme-button-color)]' : ''}`
                    : 'text-[var(--tg-theme-hint-color)]/40'
                }`}
                disabled={!entry}
                onClick={() => setSelectedDay(isSelected ? null : day)}
              >
                {day}
              </button>
            )
          })}
        </div>
      ))}

      {/* Selected day detail */}
      {selectedEntry && (
        <DayDetail
          entry={selectedEntry}
          onClose={() => setSelectedDay(null)}
        />
      )}
    </div>
  )
}

export default function HistoryScreen() {
  const user = useAuthStore((s) => s.user)
  const { barberStats, isLoading, error, fetchBarberStats } = useKombatStore()

  const now = new Date()
  const [viewYear, setViewYear] = useState(now.getFullYear())
  const [viewMonth, setViewMonth] = useState(now.getMonth() + 1)

  const monthStr = `${viewYear}-${String(viewMonth).padStart(2, '0')}`

  useEffect(() => {
    if (user?.id) {
      fetchBarberStats(user.id, monthStr)
    }
  }, [user?.id, monthStr, fetchBarberStats])

  const goToPrevMonth = () => {
    if (viewMonth === 1) {
      setViewYear(viewYear - 1)
      setViewMonth(12)
    } else {
      setViewMonth(viewMonth - 1)
    }
  }

  const goToNextMonth = () => {
    if (viewMonth === 12) {
      setViewYear(viewYear + 1)
      setViewMonth(1)
    } else {
      setViewMonth(viewMonth + 1)
    }
  }

  const isCurrentMonth =
    viewYear === now.getFullYear() && viewMonth === now.getMonth() + 1

  if (isLoading && !barberStats) {
    return (
      <div className="p-4">
        <LoadingSkeleton lines={8} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-[var(--tg-theme-destructive-text-color)]">{error}</p>
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      {/* Month navigation */}
      <div className="flex items-center justify-between px-4">
        <button
          type="button"
          className="rounded-lg px-3 py-1.5 text-[var(--tg-theme-button-color)] active:bg-[var(--tg-theme-button-color)]/10"
          onClick={goToPrevMonth}
        >
          \u{2190}
        </button>
        <h1 className="text-lg font-bold">{formatMonthYear(viewYear, viewMonth)}</h1>
        <button
          type="button"
          className={`rounded-lg px-3 py-1.5 ${
            isCurrentMonth
              ? 'text-[var(--tg-theme-hint-color)]/30'
              : 'text-[var(--tg-theme-button-color)] active:bg-[var(--tg-theme-button-color)]/10'
          }`}
          disabled={isCurrentMonth}
          onClick={goToNextMonth}
        >
          \u{2192}
        </button>
      </div>

      {/* Calendar */}
      <div className="mt-3">
        <Calendar
          year={viewYear}
          month={viewMonth}
          scores={barberStats?.daily_scores ?? []}
        />
      </div>

      {/* Monthly summary */}
      {barberStats && (
        <div className="mx-4 mt-4 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4">
          <h3 className="font-medium">Итоги месяца</h3>
          <div className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--tg-theme-hint-color)]">Побед</span>
              <span className="font-bold">{barberStats.wins}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--tg-theme-hint-color)]">Средний рейтинг</span>
              <span className="font-bold tabular-nums">{barberStats.avg_score.toFixed(1)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--tg-theme-hint-color)]">Выручка</span>
              <span className="font-bold tabular-nums">{formatMoney(barberStats.total_revenue)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--tg-theme-hint-color)]">Средний ЧС</span>
              <span className="font-bold tabular-nums">{barberStats.avg_cs.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
