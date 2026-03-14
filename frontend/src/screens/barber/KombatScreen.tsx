import { useState } from 'react'

import { MedalBadge, IconTarget } from '../../components/Icons'
import InfoSheet, { InfoButton, InfoSection, InfoMetricRow } from '../../components/InfoSheet'
import { ScoreBar, RatingDetail, formatMoney, formatDate, SEGMENT_COLORS } from '../../components/KombatComponents'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useKombatRating } from '../../hooks/useKombatRating'
import { useAuthStore } from '../../stores/authStore'
import type { RatingEntry, RatingWeights } from '../../types'

function RatingRow({
  entry,
  weights,
  isCurrentUser,
}: {
  entry: RatingEntry
  weights: RatingWeights
  isCurrentUser: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div
      className={`transition-all duration-300 ${
        isCurrentUser ? 'bk-card-glow rounded-2xl border border-[var(--bk-border-gold)]' : ''
      }`}
      style={{ order: entry.rank }}
    >
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <MedalBadge rank={entry.rank} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between">
            <span
              className={`truncate font-medium ${
                isCurrentUser ? 'text-[var(--bk-gold)]' : 'text-[var(--bk-text)]'
              }`}
            >
              {entry.name}
            </span>
            <span
              className="ml-2 font-bold tabular-nums text-lg"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {entry.total_score.toFixed(1)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <ScoreBar entry={entry} weights={weights} />
            </div>
            <span className="ml-2 text-xs tabular-nums text-[var(--bk-text-secondary)]">
              {formatMoney(entry.revenue)}
            </span>
          </div>
        </div>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ${
          expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        <div className="overflow-hidden">{expanded && <RatingDetail entry={entry} />}</div>
      </div>
    </div>
  )
}

function KombatInfoSheet({ open, onClose, weights }: { open: boolean; onClose: () => void; weights: RatingWeights }) {
  return (
    <InfoSheet open={open} onClose={onClose} title="Как работает Комбат">
      <InfoSection title="Суть соревнования">
        <p>
          Каждый день все барберы филиала соревнуются между собой. Система автоматически считает баллы
          по 5 показателям и формирует рейтинг. Топ-3 по итогам дня получают призы.
        </p>
      </InfoSection>

      <InfoSection title="Из чего складывается балл">
        <p className="mb-2">
          Итоговый балл (макс. 100) — это сумма 5 показателей. По каждому лучший в филиале получает
          максимум, остальные — пропорционально.
        </p>
        <div className="space-y-0.5">
          <InfoMetricRow
            color={SEGMENT_COLORS[0]}
            label="Выручка"
            weight={weights.revenue}
            description="Общая сумма за день. Больше клиентов и услуг — больше баллов."
          />
          <InfoMetricRow
            color={SEGMENT_COLORS[1]}
            label="Средний чек"
            weight={weights.cs}
            description="Средняя стоимость услуги относительно базовой стрижки. Доп. услуги и уходы повышают показатель."
          />
          <InfoMetricRow
            color={SEGMENT_COLORS[2]}
            label="Товары"
            weight={weights.products}
            description="Количество проданных товаров (воск, шампунь и т.д.)."
          />
          <InfoMetricRow
            color={SEGMENT_COLORS[3]}
            label="Доп. услуги"
            weight={weights.extras}
            description="Количество доп. услуг (камуфляж, уход за бородой, маска и т.д.)."
          />
          <InfoMetricRow
            color={SEGMENT_COLORS[4]}
            label="Отзывы"
            weight={weights.reviews}
            description="Средняя оценка от клиентов за день. Нет отзывов = 0 баллов."
          />
        </div>
      </InfoSection>

      <InfoSection title="Цветная полоска">
        <p>
          Полоска под именем показывает вклад каждого показателя. Яркий цвет — есть баллы, тусклый — нет.
          Нажми на барбера, чтобы увидеть детали.
        </p>
      </InfoSection>

      <InfoSection title="Призовой фонд">
        <p>
          Призы рассчитываются как процент от общей выручки филиала с 1-го числа месяца.
          Чем больше зарабатывает филиал — тем больше призы. Выплачиваются ежедневно победителям.
        </p>
      </InfoSection>

      <InfoSection title="План филиала">
        <p>
          Прогресс выполнения месячного плана выручки. Показывает, сколько осталось
          до цели и сколько нужно зарабатывать в день.
        </p>
      </InfoSection>
    </InfoSheet>
  )
}

export default function KombatScreen() {
  const { todayRating, isLoading, error } = useKombatRating()
  const user = useAuthStore((s) => s.user)
  const [infoOpen, setInfoOpen] = useState(false)

  if (isLoading && !todayRating) {
    return (
      <div className="p-4">
        <LoadingSkeleton lines={2} />
        <div className="mt-6 space-y-4">
          {Array.from({ length: 4 }, (_, i) => (
            <LoadingSkeleton key={i} lines={2} />
          ))}
        </div>
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

  if (!todayRating) return null

  const { ratings, prize_fund, plan, weights, date, branch_name, is_active } = todayRating

  return (
    <div className="pb-4">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pb-2 pt-4">
        <div>
          <h1 className="bk-heading text-xl">{branch_name}</h1>
          <p className="mt-0.5 text-sm text-[var(--bk-text-secondary)]">{formatDate(date)}</p>
        </div>
        <div className="flex items-center gap-2">
          <InfoButton onClick={() => setInfoOpen(true)} />
          {is_active && (
            <span className="bk-live-pulse flex items-center gap-1.5 rounded-full bg-[var(--bk-red)]/10 px-3 py-1.5 text-xs font-bold tracking-wider text-[var(--bk-red)]">
              <span className="inline-block h-2 w-2 rounded-full bg-[var(--bk-red)]" />
              LIVE
            </span>
          )}
        </div>
      </div>

      {/* Rating list */}
      <div className="mt-2 space-y-1 px-2">
        {ratings.map((entry) => (
          <RatingRow
            key={entry.barber_id}
            entry={entry}
            weights={weights}
            isCurrentUser={entry.barber_id === user?.id}
          />
        ))}
        {ratings.length === 0 && (
          <p className="px-4 py-8 text-center text-[var(--bk-text-secondary)]">
            Данных за сегодня пока нет
          </p>
        )}
      </div>

      {/* Prize fund */}
      <div className="mx-4 mt-5">
        <div className="grid grid-cols-3 gap-2">
          {[
            { rank: 1, amount: prize_fund.gold },
            { rank: 2, amount: prize_fund.silver },
            { rank: 3, amount: prize_fund.bronze },
          ].map((p) => (
            <div key={p.rank} className="bk-card flex flex-col items-center px-2 py-3">
              <MedalBadge rank={p.rank} size={32} />
              <span className="mt-2 text-sm font-bold tabular-nums text-[var(--bk-text)]">
                {formatMoney(p.amount)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-2 text-center text-xs text-[var(--bk-text-dim)]">
          Призовой фонд с 1-го числа
        </p>
      </div>

      {/* Plan progress */}
      {plan && (
        <div className="bk-card mx-4 mt-4 p-4">
          <div className="flex items-center gap-2">
            <IconTarget size={16} className="text-[var(--bk-gold)]" />
            <span className="text-sm font-medium text-[var(--bk-text)]">План филиала</span>
            <span
              className="ml-auto font-bold tabular-nums text-lg"
              style={{ fontFamily: 'var(--bk-font-heading)' }}
            >
              {plan.percentage.toFixed(0)}%
            </span>
          </div>
          <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-[var(--bk-bg-elevated)]">
            <div
              className="bk-progress-fill h-full transition-all duration-700"
              style={{ width: `${Math.min(plan.percentage, 100)}%` }}
            />
          </div>
          <p className="mt-2 text-sm tabular-nums text-[var(--bk-text-secondary)]">
            {formatMoney(plan.current)} из {formatMoney(plan.target)}
          </p>
          {plan.required_daily > 0 && (
            <p className="mt-0.5 text-xs text-[var(--bk-text-dim)]">
              Нужно ~{formatMoney(plan.required_daily)}/смену
            </p>
          )}
        </div>
      )}

      <KombatInfoSheet open={infoOpen} onClose={() => setInfoOpen(false)} weights={weights} />
    </div>
  )
}
