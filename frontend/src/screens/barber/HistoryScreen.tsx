import { useState, useEffect, useMemo } from 'react'

import { MedalBadge, IconArrowLeft, IconArrowRight, IconX } from '../../components/Icons'
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

function getRankClasses(rank: number): string {
  switch (rank) {
    case 1:
      return 'bk-medal-gold'
    case 2:
      return 'bk-medal-silver'
    case 3:
      return 'bk-medal-bronze'
    default:
      return 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-dim)]'
  }
}

function buildCalendarGrid(year: number, month: number): (number | null)[][] {
  const firstDay = new Date(year, month - 1, 1)
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

function DayDetail({ entry, onClose }: { entry: DailyScoreEntry; onClose: () => void }) {
  const d = new Date(entry.date + 'T00:00:00')
  const label = d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    weekday: 'short',
  })

  return (
    <div className="bk-card bk-card-glow mx-4 mt-3 p-4">
      <div className="flex items-center justify-between">
        <span className="font-medium text-[var(--bk-text)]">{label}</span>
        <button type="button" className="text-[var(--bk-text-dim)]" onClick={onClose}>
          <IconX size={16} />
        </button>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <span className="text-xs text-[var(--bk-text-secondary)]">Место</span>
          <div className="mt-1">
            <MedalBadge rank={entry.rank} size={36} />
          </div>
        </div>
        <div>
          <span className="text-xs text-[var(--bk-text-secondary)]">Рейтинг</span>
          <p
            className="mt-1 text-2xl font-bold tabular-nums"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {entry.score.toFixed(1)}
          </p>
        </div>
      </div>
    </div>
  )
}

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
      <div className="grid grid-cols-7 px-4">
        {WEEKDAY_LABELS.map((d) => (
          <div
            key={d}
            className="py-1 text-center text-[10px] font-medium uppercase tracking-wider text-[var(--bk-text-dim)]"
          >
            {d}
          </div>
        ))}
      </div>

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
                className={`mx-auto my-0.5 flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold transition-all ${
                  entry
                    ? `${getRankClasses(entry.rank)} ${isSelected ? 'ring-2 ring-[var(--bk-gold)] ring-offset-1 ring-offset-[var(--bk-bg-primary)]' : ''}`
                    : 'text-[var(--bk-text-dim)]/30'
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

      {selectedEntry && <DayDetail entry={selectedEntry} onClose={() => setSelectedDay(null)} />}
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

  const isCurrentMonth = viewYear === now.getFullYear() && viewMonth === now.getMonth() + 1

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
        <p className="text-[var(--bk-red)]">{error}</p>
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      {/* Month navigation */}
      <div className="flex items-center justify-between px-4">
        <button
          type="button"
          className="rounded-lg p-2 text-[var(--bk-gold)] active:bg-[var(--bk-gold)]/10"
          onClick={goToPrevMonth}
        >
          <IconArrowLeft size={20} />
        </button>
        <h1 className="bk-heading text-lg">{formatMonthYear(viewYear, viewMonth)}</h1>
        <button
          type="button"
          className={`rounded-lg p-2 ${
            isCurrentMonth
              ? 'text-[var(--bk-text-dim)]/30'
              : 'text-[var(--bk-gold)] active:bg-[var(--bk-gold)]/10'
          }`}
          disabled={isCurrentMonth}
          onClick={goToNextMonth}
        >
          <IconArrowRight size={20} />
        </button>
      </div>

      <div className="mt-3">
        <Calendar year={viewYear} month={viewMonth} scores={barberStats?.daily_scores ?? []} />
      </div>

      {barberStats && (
        <div className="bk-card mx-4 mt-4 p-4">
          <h3 className="bk-heading text-base">Итоги месяца</h3>
          <div className="mt-3 space-y-2.5 text-sm">
            {[
              { label: 'Побед', value: String(barberStats.wins) },
              { label: 'Средний рейтинг', value: barberStats.avg_score.toFixed(1) },
              { label: 'Выручка', value: formatMoney(barberStats.total_revenue) },
              { label: 'Средний ЧС', value: barberStats.avg_cs.toFixed(2) },
            ].map((s) => (
              <div key={s.label} className="flex justify-between">
                <span className="text-[var(--bk-text-secondary)]">{s.label}</span>
                <span className="font-bold tabular-nums text-[var(--bk-text)]">{s.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
