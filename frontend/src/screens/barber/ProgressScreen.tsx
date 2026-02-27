import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useKombatRating } from '../../hooks/useKombatRating'
import { usePVRProgress } from '../../hooks/usePVRProgress'
import { useKombatStore } from '../../stores/kombatStore'
import { useAuthStore } from '../../stores/authStore'
import { useEffect } from 'react'
import type { PVRThreshold } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  if (rubles >= 1000) {
    return (rubles / 1000).toFixed(rubles % 1000 === 0 ? 0 : 1) + '\u{00A0}тыс\u{00A0}\u{20BD}'
  }
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

function formatMoneyShort(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

// Vertical PVR scale with thresholds
function PVRScale({
  thresholds,
  cumulative,
  currentThreshold,
  nextThreshold,
  remainingToNext,
  bonusAmount,
}: {
  thresholds: PVRThreshold[]
  cumulative: number
  currentThreshold: number | null
  nextThreshold: number | null
  remainingToNext: number | null
  bonusAmount: number
}) {
  if (thresholds.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-[var(--tg-theme-hint-color)]">
        Пороги ПВР не настроены
      </p>
    )
  }

  const sorted = [...thresholds].sort((a, b) => a.amount - b.amount)
  const maxAmount = sorted[sorted.length - 1].amount

  return (
    <div className="relative ml-4 mr-4">
      {/* Current amount badge at top */}
      <div className="mb-4 text-center">
        <span className="text-2xl font-bold tabular-nums">{formatMoneyShort(cumulative)}</span>
        {bonusAmount > 0 && (
          <p className="text-sm text-[var(--tg-theme-button-color)]">
            Премия: {formatMoneyShort(bonusAmount)}
          </p>
        )}
      </div>

      {/* Vertical track */}
      <div className="relative ml-6">
        {/* Track line */}
        <div className="absolute left-3 top-0 h-full w-0.5 bg-[var(--tg-theme-hint-color)]/20" />

        {/* Fill line up to current position */}
        <div
          className="absolute left-3 bottom-0 w-0.5 bg-[var(--tg-theme-button-color)] transition-all duration-700"
          style={{
            height: `${Math.min((cumulative / maxAmount) * 100, 100)}%`,
          }}
        />

        {/* Threshold markers (rendered bottom to top) */}
        <div className="flex flex-col-reverse gap-6 pb-2 pt-2">
          {sorted.map((t) => {
            const reached = cumulative >= t.amount
            const isNext = t.amount === nextThreshold
            const isCurrent = t.amount === currentThreshold

            return (
              <div key={t.amount} className="relative flex items-center gap-3 pl-0">
                {/* Dot marker */}
                <div
                  className={`relative z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 transition-colors ${
                    reached
                      ? 'border-[var(--tg-theme-button-color)] bg-[var(--tg-theme-button-color)]'
                      : isNext
                        ? 'border-[var(--tg-theme-button-color)] bg-[var(--tg-theme-bg-color)]'
                        : 'border-[var(--tg-theme-hint-color)]/40 bg-[var(--tg-theme-bg-color)]'
                  }`}
                >
                  {reached && (
                    <svg className="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none">
                      <path
                        d="M2 6l3 3 5-5"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                </div>

                {/* Label */}
                <div className="flex-1">
                  <div className="flex items-baseline justify-between">
                    <span
                      className={`text-sm font-medium ${
                        isNext
                          ? 'text-[var(--tg-theme-button-color)]'
                          : reached
                            ? 'text-[var(--tg-theme-text-color)]'
                            : 'text-[var(--tg-theme-hint-color)]'
                      }`}
                    >
                      {formatMoney(t.amount)}
                    </span>
                    <span
                      className={`text-sm tabular-nums ${
                        reached
                          ? 'font-medium text-[var(--tg-theme-button-color)]'
                          : 'text-[var(--tg-theme-hint-color)]'
                      }`}
                    >
                      +{formatMoneyShort(t.bonus)}
                    </span>
                  </div>
                  {isNext && remainingToNext !== null && (
                    <p className="text-xs text-[var(--tg-theme-button-color)]">
                      Осталось: {formatMoneyShort(remainingToNext)}
                    </p>
                  )}
                  {isCurrent && reached && (
                    <p className="text-xs text-[var(--tg-theme-hint-color)]">Текущий порог</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// Monthly stats card
function MonthStats({
  wins,
  avgScore,
  avgCs,
  totalProducts,
  totalExtras,
}: {
  wins: number
  avgScore: number
  avgCs: number
  totalProducts: number
  totalExtras: number
}) {
  const stats = [
    { label: 'Побед в Комбате', value: String(wins) },
    { label: 'Средний рейтинг', value: avgScore.toFixed(1) },
    { label: 'Средний ЧС', value: avgCs.toFixed(2) },
    { label: 'Товаров продано', value: String(totalProducts) },
    { label: 'Допов оказано', value: String(totalExtras) },
  ]

  return (
    <div className="mx-4 mt-4 rounded-xl bg-[var(--tg-theme-secondary-bg-color)] p-4">
      <h3 className="mb-3 font-medium">Статистика месяца</h3>
      <div className="space-y-2.5">
        {stats.map((s) => (
          <div key={s.label} className="flex items-baseline justify-between">
            <span className="text-sm text-[var(--tg-theme-hint-color)]">{s.label}</span>
            <span className="font-bold tabular-nums">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ProgressScreen() {
  const { barberPvr, thresholds, isLoading: pvrLoading, error: pvrError } = usePVRProgress()
  const user = useAuthStore((s) => s.user)
  const { barberStats, fetchBarberStats } = useKombatStore()

  // Also load kombat rating context for real-time
  useKombatRating()

  useEffect(() => {
    if (user?.id) {
      fetchBarberStats(user.id)
    }
  }, [user?.id, fetchBarberStats])

  if (pvrLoading && !barberPvr) {
    return (
      <div className="p-4">
        <LoadingSkeleton lines={6} />
      </div>
    )
  }

  if (pvrError) {
    return (
      <div className="flex flex-col items-center gap-3 p-8 text-center">
        <p className="text-[var(--tg-theme-destructive-text-color)]">{pvrError}</p>
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      <h1 className="px-4 text-lg font-bold">Прогресс</h1>

      {/* PVR Scale */}
      {barberPvr && (
        <div className="mt-4">
          <PVRScale
            thresholds={thresholds}
            cumulative={barberPvr.cumulative_revenue}
            currentThreshold={barberPvr.current_threshold}
            nextThreshold={barberPvr.next_threshold}
            remainingToNext={barberPvr.remaining_to_next}
            bonusAmount={barberPvr.bonus_amount}
          />
        </div>
      )}

      {/* Month stats */}
      {barberStats && (
        <MonthStats
          wins={barberStats.wins}
          avgScore={barberStats.avg_score}
          avgCs={barberStats.avg_cs}
          totalProducts={barberStats.total_products}
          totalExtras={barberStats.total_extras}
        />
      )}
    </div>
  )
}
