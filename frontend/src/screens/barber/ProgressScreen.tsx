import { useEffect, useState } from 'react'

import { IconCheck, IconCrown, IconFlame } from '../../components/Icons'
import InfoSheet, { InfoButton, InfoSection } from '../../components/InfoSheet'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useKombatRating } from '../../hooks/useKombatRating'
import { usePVRProgress } from '../../hooks/usePVRProgress'
import { useKombatStore } from '../../stores/kombatStore'
import { useAuthStore } from '../../stores/authStore'
import type { MetricBreakdown, PVRThreshold } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

const METRIC_LABELS: { key: keyof MetricBreakdown; label: string; hint: string }[] = [
  { key: 'revenue_score', label: 'Выручка', hint: 'сумма твоей выручки за месяц' },
  { key: 'cs_score', label: 'Средний чек', hint: 'во сколько раз чек выше базовой стрижки' },
  { key: 'products_score', label: 'Товары', hint: 'сколько товаров продал' },
  { key: 'extras_score', label: 'Доп. услуги', hint: 'сколько допуслуг оказал' },
  { key: 'reviews_score', label: 'Отзывы', hint: 'средняя оценка клиентов' },
]

function RatingGauge({
  score,
  currentThreshold,
  nextThreshold,
  remainingToNext,
  bonusAmount,
  thresholds,
}: {
  score: number
  currentThreshold: number | null
  nextThreshold: number | null
  remainingToNext: number | null
  bonusAmount: number
  thresholds: PVRThreshold[]
}) {
  const clamped = Math.max(0, Math.min(100, score))

  return (
    <div className="mx-4">
      <div className="text-center">
        <p className="text-xs uppercase tracking-wider text-[var(--bk-text-dim)]">
          Рейтинг месяца
        </p>
        <div className="mt-1 flex items-baseline justify-center gap-1">
          <span
            className="text-5xl font-bold tabular-nums text-[var(--bk-text)]"
            style={{ fontFamily: 'var(--bk-font-heading)' }}
          >
            {clamped}
          </span>
          <span className="text-lg text-[var(--bk-text-dim)]">/ 100</span>
        </div>
        {bonusAmount > 0 && (
          <p className="mt-1 text-sm font-semibold text-[var(--bk-gold)]">
            Текущая премия: {formatMoney(bonusAmount)}
          </p>
        )}
        {nextThreshold !== null && remainingToNext !== null && (
          <p className="mt-1 text-xs text-[var(--bk-text-secondary)]">
            До {nextThreshold} баллов: +{remainingToNext}
          </p>
        )}
      </div>

      <div className="mt-4 h-3 w-full overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{
            width: `${clamped}%`,
            background: 'linear-gradient(to right, var(--bk-gold-dim), var(--bk-gold))',
          }}
        />
      </div>

      {thresholds.length > 0 && (
        <div className="mt-3 space-y-1.5">
          {[...thresholds]
            .sort((a, b) => a.score - b.score)
            .map((t) => {
              const reached = clamped >= t.score
              const isCurrent = t.score === currentThreshold
              const isNext = t.score === nextThreshold
              return (
                <div key={t.score} className="flex items-center gap-2 text-sm">
                  <div
                    className={`flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border-2 ${
                      reached
                        ? 'border-[var(--bk-gold)] bg-[var(--bk-gold)]'
                        : isNext
                          ? 'border-[var(--bk-gold)] bg-[var(--bk-bg-primary)]'
                          : 'border-[var(--bk-text-dim)] bg-[var(--bk-bg-primary)]'
                    }`}
                  >
                    {reached && <IconCheck size={10} className="text-[var(--bk-bg-primary)]" />}
                  </div>
                  <span
                    className={
                      isNext
                        ? 'text-[var(--bk-gold)]'
                        : reached
                          ? 'text-[var(--bk-text)]'
                          : 'text-[var(--bk-text-secondary)]'
                    }
                  >
                    {t.score} баллов
                  </span>
                  <span className="ml-auto tabular-nums">
                    <span
                      className={
                        reached
                          ? 'font-semibold text-[var(--bk-gold)]'
                          : 'text-[var(--bk-text-secondary)]'
                      }
                    >
                      +{formatMoney(t.bonus)}
                    </span>
                    {isCurrent && reached && (
                      <span className="ml-2 text-[10px] uppercase text-[var(--bk-text-dim)]">
                        текущий
                      </span>
                    )}
                  </span>
                </div>
              )
            })}
        </div>
      )}
    </div>
  )
}

function MetricBars({ breakdown }: { breakdown: MetricBreakdown }) {
  const weakest = METRIC_LABELS.reduce(
    (acc, m) => (breakdown[m.key] < breakdown[acc.key] ? m : acc),
    METRIC_LABELS[0],
  )

  return (
    <div className="bk-card mx-4 mt-5 p-4">
      <h3 className="bk-heading text-base">Из чего складывается рейтинг</h3>
      <p className="mt-0.5 text-[11px] text-[var(--bk-text-dim)]">
        Каждая метрика — от 0 до 100 относительно филиала
      </p>
      <div className="mt-3 space-y-2.5">
        {METRIC_LABELS.map((m) => {
          const v = breakdown[m.key] ?? 0
          const isWeakest = m.key === weakest.key && v < 80
          return (
            <div key={m.key}>
              <div className="flex items-baseline justify-between">
                <span className="text-sm text-[var(--bk-text)]">{m.label}</span>
                <span className="text-sm font-semibold tabular-nums text-[var(--bk-text)]">
                  {v}
                </span>
              </div>
              <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(0, Math.min(100, v))}%`,
                    background: isWeakest
                      ? 'var(--bk-red)'
                      : 'linear-gradient(to right, var(--bk-gold-dim), var(--bk-gold))',
                  }}
                />
              </div>
              {isWeakest && (
                <p className="mt-0.5 text-[11px] text-[var(--bk-red)]">
                  Слабая метрика — {m.hint}
                </p>
              )}
            </div>
          )
        })}
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
  cumulativeRevenue,
}: {
  wins: number
  avgScore: number
  avgCs: number
  totalProducts: number
  totalExtras: number
  cumulativeRevenue: number
}) {
  const stats = [
    {
      icon: <IconCrown size={16} className="text-[var(--bk-gold)]" />,
      label: 'Первых мест',
      hint: 'дней на 1-м месте в рейтинге',
      value: String(wins),
    },
    {
      icon: <IconFlame size={16} className="text-[var(--bk-score-cs)]" />,
      label: 'Средний дневной балл',
      hint: 'из 100 возможных за день',
      value: avgScore.toFixed(1),
    },
    {
      icon: null,
      label: 'Средний чек',
      hint: avgCs >= 1 ? 'выше базовой стрижки' : 'ниже базовой стрижки',
      value: `\u00D7${avgCs.toFixed(2)}`,
    },
    { icon: null, label: 'Товаров продано', hint: null, value: String(totalProducts) },
    { icon: null, label: 'Доп. услуг оказано', hint: null, value: String(totalExtras) },
    { icon: null, label: 'Выручка за месяц', hint: null, value: formatMoney(cumulativeRevenue) },
  ]

  return (
    <div className="bk-card mx-4 mt-5 p-4">
      <h3 className="bk-heading text-base">Статистика месяца</h3>
      <div className="mt-3 space-y-3">
        {stats.map((s) => (
          <div key={s.label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {s.icon && <span className="flex-shrink-0">{s.icon}</span>}
              <div>
                <span className="text-sm text-[var(--bk-text-secondary)]">{s.label}</span>
                {s.hint && (
                  <p className="text-[10px] leading-tight text-[var(--bk-text-dim)]">{s.hint}</p>
                )}
              </div>
            </div>
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
      <InfoSection title="Как начисляется премия">
        <p>
          Премия зависит от твоего <strong>месячного рейтинга</strong> — шкалы от 0 до 100.
          Рейтинг учитывает не только выручку, но и средний чек, продажи товаров,
          допуслуги и отзывы. Это значит, что мастер с неполной записью, но классным
          сервисом, тоже может получить премию.
        </p>
      </InfoSection>

      <InfoSection title="Из чего складывается рейтинг">
        <p>
          Пять метрик нормализуются от 0 до 100 относительно всего филиала, потом
          складываются по весам, которые настраивает владелец. Итог — твой месячный балл.
        </p>
      </InfoSection>

      <InfoSection title="Что подтянуть">
        <p>
          Смотри на бар-чарт метрик — самая слабая выделена красным. Подтянув именно её,
          можно заметно поднять общий рейтинг, потому что ты растёшь относительно коллег
          в отстающей метрике.
        </p>
      </InfoSection>

      <InfoSection title="Минимум рабочих дней">
        <p>
          Если за месяц отработал меньше минимума, установленного владельцем, премия не
          начисляется — чтобы один удачный день не превращался в полный бонус.
        </p>
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

  const blocked =
    barberPvr &&
    barberPvr.min_visits_required > 0 &&
    barberPvr.working_days < barberPvr.min_visits_required

  return (
    <div className="pb-4 pt-4">
      <div className="flex items-center justify-between px-4">
        <h1 className="bk-heading text-xl">Прогресс</h1>
        <InfoButton onClick={() => setInfoOpen(true)} />
      </div>

      {blocked && barberPvr && (
        <div className="mx-4 mt-4 rounded-xl border border-[var(--bk-gold)] bg-[var(--bk-bg-elevated)] p-3">
          <p className="text-sm font-semibold text-[var(--bk-gold)]">
            До допуска к премии — {barberPvr.min_visits_required - barberPvr.working_days} раб.
            дня
          </p>
          <p className="mt-1 text-xs text-[var(--bk-text-secondary)]">
            Отработал в этом месяце {barberPvr.working_days} из {barberPvr.min_visits_required}.
          </p>
        </div>
      )}

      {barberPvr && (
        <div className="mt-4">
          <RatingGauge
            score={barberPvr.monthly_rating_score}
            currentThreshold={barberPvr.current_threshold}
            nextThreshold={barberPvr.next_threshold}
            remainingToNext={barberPvr.remaining_to_next}
            bonusAmount={barberPvr.bonus_amount}
            thresholds={thresholds}
          />
          <MetricBars breakdown={barberPvr.metric_breakdown} />
        </div>
      )}

      {barberStats && barberPvr && (
        <MonthStats
          wins={barberStats.wins}
          avgScore={barberStats.avg_score}
          avgCs={barberStats.avg_cs}
          totalProducts={barberStats.total_products}
          totalExtras={barberStats.total_extras}
          cumulativeRevenue={barberPvr.cumulative_revenue}
        />
      )}

      <ProgressInfoSheet open={infoOpen} onClose={() => setInfoOpen(false)} />
    </div>
  )
}
