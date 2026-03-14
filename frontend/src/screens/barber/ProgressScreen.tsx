import { useEffect, useState, useMemo } from 'react'

import { IconCheck, IconFlame, IconCrown } from '../../components/Icons'
import InfoSheet, { InfoButton, InfoSection } from '../../components/InfoSheet'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useKombatRating } from '../../hooks/useKombatRating'
import { usePVRProgress } from '../../hooks/usePVRProgress'
import { useKombatStore } from '../../stores/kombatStore'
import { useAuthStore } from '../../stores/authStore'
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

function PVRScale({
  thresholds,
  cumulative,
  currentThreshold,
  nextThreshold,
  remainingToNext,
  bonusAmount,
  todayRevenue,
}: {
  thresholds: PVRThreshold[]
  cumulative: number
  currentThreshold: number | null
  nextThreshold: number | null
  remainingToNext: number | null
  bonusAmount: number
  todayRevenue: number | null
}) {
  if (thresholds.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-[var(--bk-text-secondary)]">
        Пороги премий не настроены
      </p>
    )
  }

  const sorted = [...thresholds].sort((a, b) => a.amount - b.amount)
  const n = sorted.length

  // Calculate fill percentage interpolated by threshold positions (not raw amounts).
  // Thresholds are evenly spaced visually, so we map cumulative to the segment it falls into.
  let fillPercent = 0
  if (cumulative >= sorted[n - 1].amount) {
    fillPercent = 100
  } else if (n === 1) {
    fillPercent = Math.min((cumulative / sorted[0].amount) * 100, 100)
  } else if (cumulative > 0) {
    if (cumulative < sorted[0].amount) {
      // Below first threshold — small proportional fill
      fillPercent = (cumulative / sorted[0].amount) * (1 / (n - 1)) * 100 * 0.5
    } else {
      for (let i = 0; i < n - 1; i++) {
        if (cumulative < sorted[i + 1].amount) {
          const segProgress = (cumulative - sorted[i].amount) / (sorted[i + 1].amount - sorted[i].amount)
          fillPercent = ((i + segProgress) / (n - 1)) * 100
          break
        }
      }
    }
  }

  return (
    <div className="relative mx-4">
      {/* Current amount badge */}
      <div className="mb-5 text-center">
        <span
          className="text-3xl font-bold tabular-nums"
          style={{ fontFamily: 'var(--bk-font-heading)' }}
        >
          {formatMoneyShort(cumulative)}
        </span>
        {todayRevenue !== null && todayRevenue > 0 && (
          <p className="mt-1 text-sm text-[var(--bk-text-secondary)]">
            Сегодня: +{formatMoneyShort(todayRevenue)}
          </p>
        )}
        {bonusAmount > 0 && (
          <p className="mt-1 text-sm font-semibold text-[var(--bk-gold)]">
            Премия: {formatMoneyShort(bonusAmount)}
          </p>
        )}
      </div>

      {/* Vertical track */}
      <div className="relative ml-6">
        <div className="absolute left-3 top-0 h-full w-0.5 bg-[var(--bk-bg-elevated)]" />
        <div
          className="absolute left-3 bottom-0 w-0.5 transition-all duration-700"
          style={{
            height: `${fillPercent}%`,
            background: 'linear-gradient(to top, var(--bk-gold-dim), var(--bk-gold))',
          }}
        />

        <div className="flex flex-col-reverse gap-6 pb-2 pt-2">
          {sorted.map((t) => {
            const reached = cumulative >= t.amount
            const isNext = t.amount === nextThreshold
            const isCurrent = t.amount === currentThreshold

            return (
              <div key={t.amount} className="relative flex items-center gap-3 pl-0">
                <div
                  className={`relative z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 transition-colors ${
                    reached
                      ? 'border-[var(--bk-gold)] bg-[var(--bk-gold)]'
                      : isNext
                        ? 'border-[var(--bk-gold)] bg-[var(--bk-bg-primary)]'
                        : 'border-[var(--bk-text-dim)] bg-[var(--bk-bg-primary)]'
                  }`}
                >
                  {reached && <IconCheck size={12} className="text-[var(--bk-bg-primary)]" />}
                </div>

                <div className="flex-1">
                  <div className="flex items-baseline justify-between">
                    <span
                      className={`text-sm font-medium ${
                        isNext
                          ? 'text-[var(--bk-gold)]'
                          : reached
                            ? 'text-[var(--bk-text)]'
                            : 'text-[var(--bk-text-secondary)]'
                      }`}
                    >
                      {formatMoney(t.amount)}
                    </span>
                    <span
                      className={`text-sm tabular-nums ${
                        reached
                          ? 'font-semibold text-[var(--bk-gold)]'
                          : 'text-[var(--bk-text-secondary)]'
                      }`}
                    >
                      +{formatMoneyShort(t.bonus)}
                    </span>
                  </div>
                  {isNext && remainingToNext !== null && (
                    <p className="text-xs text-[var(--bk-gold)]">
                      Осталось: {formatMoneyShort(remainingToNext)}
                    </p>
                  )}
                  {isCurrent && reached && (
                    <p className="text-xs text-[var(--bk-text-dim)]">Текущий порог</p>
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
    {
      icon: <IconCrown size={16} className="text-[var(--bk-gold)]" />,
      label: 'Побед в Комбате',
      value: String(wins),
    },
    {
      icon: <IconFlame size={16} className="text-[var(--bk-score-cs)]" />,
      label: 'Средний рейтинг',
      value: avgScore.toFixed(1),
    },
    { icon: null, label: 'Средний чек', value: `×${avgCs.toFixed(2)}` },
    { icon: null, label: 'Товаров продано', value: String(totalProducts) },
    { icon: null, label: 'Доп. услуг оказано', value: String(totalExtras) },
  ]

  return (
    <div className="bk-card mx-4 mt-5 p-4">
      <h3 className="bk-heading text-base">Статистика месяца</h3>
      <div className="mt-3 space-y-3">
        {stats.map((s) => (
          <div key={s.label} className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm text-[var(--bk-text-secondary)]">
              {s.icon}
              {s.label}
            </span>
            <span className="font-bold tabular-nums text-[var(--bk-text)]">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ProgressInfoSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <InfoSheet open={open} onClose={onClose} title="Прогресс и премии">
      <InfoSection title="Как работают премии за выручку?">
        <p>
          Это система бонусов за твою накопительную выручку за месяц.
          Чем больше заработал — тем выше премия. Всё просто.
        </p>
      </InfoSection>

      <InfoSection title="Как работают пороги">
        <p>
          Слева — шкала с порогами выручки. Когда твоя суммарная выручка за месяц
          достигает очередного порога — ты получаешь премию. Каждый следующий порог выше,
          но и премия больше.
        </p>
      </InfoSection>

      <InfoSection title="Что считается в выручку">
        <p>
          Все завершённые визиты за текущий месяц: стрижки, доп. услуги, продажа товаров.
          Чем больше услуг и продаж — тем быстрее растёт накопительная сумма.
        </p>
      </InfoSection>

      <InfoSection title="Статистика месяца">
        <p className="mb-1.5">Внизу — твои итоги за текущий месяц:</p>
        <ul className="list-inside list-disc space-y-1">
          <li><strong>Побед</strong> — сколько раз ты был #1 в дневном рейтинге</li>
          <li><strong>Средний рейтинг</strong> — средний балл за все рабочие дни</li>
          <li><strong>Средний чек</strong> — во сколько раз средний визит дороже базовой стрижки. ×1.0 = только стрижка, ×2.0 = вдвое дороже (допы, уходы)</li>
          <li><strong>Товары</strong> — сколько товаров продано за месяц</li>
          <li><strong>Доп. услуги</strong> — сколько доп. услуг оказано за месяц</li>
        </ul>
      </InfoSection>
    </InfoSheet>
  )
}

export default function ProgressScreen() {
  const { barberPvr, thresholds, isLoading: pvrLoading, error: pvrError } = usePVRProgress()
  const user = useAuthStore((s) => s.user)
  const { barberStats, fetchBarberStats } = useKombatStore()
  const [infoOpen, setInfoOpen] = useState(false)

  useKombatRating()

  useEffect(() => {
    if (user?.id) {
      fetchBarberStats(user.id)
    }
  }, [user?.id, fetchBarberStats])

  const todayRevenue = useMemo(() => {
    if (!barberStats?.daily_scores?.length) return null
    const today = new Date().toISOString().slice(0, 10)
    const todayEntry = barberStats.daily_scores.find((d) => d.date === today)
    return todayEntry?.revenue ?? null
  }, [barberStats])

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
        <p className="text-[var(--bk-red)]">{pvrError}</p>
      </div>
    )
  }

  return (
    <div className="pb-4 pt-4">
      <div className="flex items-center justify-between px-4">
        <h1 className="bk-heading text-xl">Прогресс</h1>
        <InfoButton onClick={() => setInfoOpen(true)} />
      </div>

      {barberPvr && (
        <div className="mt-4">
          <PVRScale
            thresholds={thresholds}
            cumulative={barberPvr.cumulative_revenue}
            currentThreshold={barberPvr.current_threshold}
            nextThreshold={barberPvr.next_threshold}
            remainingToNext={barberPvr.remaining_to_next}
            bonusAmount={barberPvr.bonus_amount}
            todayRevenue={todayRevenue}
          />
        </div>
      )}

      {barberStats && (
        <MonthStats
          wins={barberStats.wins}
          avgScore={barberStats.avg_score}
          avgCs={barberStats.avg_cs}
          totalProducts={barberStats.total_products}
          totalExtras={barberStats.total_extras}
        />
      )}

      <ProgressInfoSheet open={infoOpen} onClose={() => setInfoOpen(false)} />
    </div>
  )
}
