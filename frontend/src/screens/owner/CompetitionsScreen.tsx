import { useEffect, useState, useCallback, useMemo } from 'react'

import { MedalBadge, IconArrowLeft, IconArrowRight } from '../../components/Icons'
import InfoSheet, { InfoButton, InfoSection, InfoMetricRow } from '../../components/InfoSheet'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useWebSocket } from '../../hooks/useWebSocket'
import { useKombatStore } from '../../stores/kombatStore'
import { useOwnerStore } from '../../stores/ownerStore'
import { usePvrStore } from '../../stores/pvrStore'
import type { RatingEntry, RatingWeights, BarberPVRResponse, WSMessage } from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

const SEGMENT_COLORS = [
  'bg-[var(--bk-score-revenue)]',
  'bg-[var(--bk-score-cs)]',
  'bg-[var(--bk-score-products)]',
  'bg-[var(--bk-score-extras)]',
  'bg-[var(--bk-score-reviews)]',
]

const SEGMENT_LABELS = ['Выручка', 'Ср. чек', 'Товары', 'Доп. услуги', 'Отзывы']

type Tab = 'kombat' | 'pvr'

function BreakdownRow({
  idx,
  label,
  score,
  rawLabel,
  weight,
}: {
  idx: number
  label: string
  score: number
  rawLabel?: string
  weight?: number
}) {
  const pct = Math.max(0, Math.min(100, score))
  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={`h-2 w-2 flex-shrink-0 rounded-full ${SEGMENT_COLORS[idx]}`}
      />
      <span className="w-20 text-[var(--bk-text-secondary)]">{label}</span>
      <div className="h-1 flex-1 overflow-hidden rounded-full bg-[var(--bk-bg-primary)]">
        <div className={`h-full ${SEGMENT_COLORS[idx]}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right tabular-nums font-semibold text-[var(--bk-text)]">
        {score.toFixed(0)}
      </span>
      {rawLabel && (
        <span className="w-20 text-right tabular-nums text-[var(--bk-text-dim)]">
          {rawLabel}
        </span>
      )}
      {weight !== undefined && (
        <span className="w-10 text-right tabular-nums text-[var(--bk-text-dim)]">
          {weight}%
        </span>
      )}
    </div>
  )
}

function getCurrentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function formatMonthLabel(month: string): string {
  return new Date(month + '-01').toLocaleDateString('ru-RU', {
    month: 'long',
    year: 'numeric',
  })
}

function RatingRow({ entry, weights }: { entry: RatingEntry; weights: RatingWeights }) {
  const [expanded, setExpanded] = useState(false)
  const segments = [
    { weight: weights.revenue, score: entry.revenue_score },
    { weight: weights.cs, score: entry.cs_score },
    { weight: weights.products, score: entry.products_score },
    { weight: weights.extras, score: entry.extras_score },
    { weight: weights.reviews, score: entry.reviews_score },
  ]

  return (
    <div className="px-3 py-2.5">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <MedalBadge rank={entry.rank} size={24} />
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between">
            <span className="truncate text-sm font-medium text-[var(--bk-text)]">
              {entry.name}
            </span>
            <div className="ml-1 flex items-baseline gap-2">
              <span className="text-xs tabular-nums text-[var(--bk-text-secondary)]">
                {formatMoney(entry.revenue)}
              </span>
              <span className="font-bold tabular-nums text-[var(--bk-text)]">
                {entry.total_score.toFixed(1)}
              </span>
            </div>
          </div>
          <div className="mt-0.5 flex h-1 gap-px overflow-hidden rounded-full">
            {segments.map((s, i) => (
              <div
                key={i}
                className={SEGMENT_COLORS[i]}
                style={{ width: `${s.weight}%`, opacity: s.score > 0 ? 1 : 0.15 }}
              />
            ))}
          </div>
        </div>
      </button>

      {expanded && (
        <div className="mt-2 space-y-1.5 rounded-lg bg-[var(--bk-bg-elevated)] p-2">
          <BreakdownRow
            idx={0}
            label="Выручка"
            score={entry.revenue_score}
            rawLabel={formatMoney(entry.revenue)}
            weight={weights.revenue}
          />
          <BreakdownRow
            idx={1}
            label="Ср. чек"
            score={entry.cs_score}
            rawLabel={`\u00D7${entry.cs_value.toFixed(2)}`}
            weight={weights.cs}
          />
          <BreakdownRow
            idx={2}
            label="Товары"
            score={entry.products_score}
            rawLabel={`${entry.products_count} шт`}
            weight={weights.products}
          />
          <BreakdownRow
            idx={3}
            label="Доп. услуги"
            score={entry.extras_score}
            rawLabel={`${entry.extras_count} шт`}
            weight={weights.extras}
          />
          <BreakdownRow
            idx={4}
            label="Отзывы"
            score={entry.reviews_score}
            rawLabel={
              entry.reviews_avg !== null ? `${entry.reviews_avg.toFixed(1)}\u2605` : '—'
            }
            weight={weights.reviews}
          />
        </div>
      )}
    </div>
  )
}

function PVRRow({
  barber,
  weights,
}: {
  barber: BarberPVRResponse
  weights: RatingWeights | null
}) {
  const [expanded, setExpanded] = useState(false)
  const blocked =
    barber.min_visits_required > 0 && barber.working_days < barber.min_visits_required
  const lastReached = barber.thresholds_reached[barber.thresholds_reached.length - 1]
  const b = barber.metric_breakdown

  return (
    <div className="px-3 py-2.5">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="text-sm font-medium text-[var(--bk-text)]">{barber.name}</span>
        <div className="text-right">
          <span className="text-sm font-bold tabular-nums text-[var(--bk-text)]">
            {barber.monthly_rating_score}
          </span>
          <span className="text-xs text-[var(--bk-text-dim)]"> / 100</span>
        </div>
      </button>

      {barber.bonus_amount > 0 && (
        <div className="mt-1 flex items-center justify-between">
          <span className="text-xs text-[var(--bk-text-dim)]">
            {lastReached
              ? `Достигнут порог ${lastReached.score} баллов`
              : `Текущий порог ${barber.current_threshold ?? 0} баллов`}
          </span>
          <span className="text-xs font-semibold text-[var(--bk-gold)]">
            Премия: +{formatMoney(barber.bonus_amount)}
          </span>
        </div>
      )}
      {barber.bonus_amount === 0 &&
        !blocked &&
        barber.next_threshold !== null &&
        barber.remaining_to_next !== null && (
          <div className="mt-1">
            <span className="text-xs text-[var(--bk-text-dim)]">
              До {barber.next_threshold} баллов: +{barber.remaining_to_next}
            </span>
          </div>
        )}
      {blocked && (
        <div className="mt-1">
          <span className="text-xs text-[var(--bk-red)]">
            Не допущен — {barber.min_visits_required - barber.working_days} раб. дн. до минимума
          </span>
        </div>
      )}
      <p className="mt-1 text-[10px] text-[var(--bk-text-dim)]">
        Выручка месяца: {formatMoney(barber.cumulative_revenue)} · Рабочих дней:{' '}
        {barber.working_days}
      </p>

      {expanded && (
        <div className="mt-2 space-y-1.5 rounded-lg bg-[var(--bk-bg-elevated)] p-2">
          <BreakdownRow
            idx={0}
            label="Выручка"
            score={b.revenue_score}
            weight={weights?.revenue}
          />
          <BreakdownRow
            idx={1}
            label="Ср. чек"
            score={b.cs_score}
            weight={weights?.cs}
          />
          <BreakdownRow
            idx={2}
            label="Товары"
            score={b.products_score}
            weight={weights?.products}
          />
          <BreakdownRow
            idx={3}
            label="Доп. услуги"
            score={b.extras_score}
            weight={weights?.extras}
          />
          <BreakdownRow
            idx={4}
            label="Отзывы"
            score={b.reviews_score}
            weight={weights?.reviews}
          />
          <p className="mt-1 text-[10px] text-[var(--bk-text-dim)]">
            Каждая метрика нормализована 0–100 относительно филиала, умножается на
            вес, сумма = итог.
          </p>
        </div>
      )}
    </div>
  )
}

export default function CompetitionsScreen() {
  const [tab, setTab] = useState<Tab>('kombat')
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null)
  const [infoOpen, setInfoOpen] = useState(false)
  const [pvrMonth, setPvrMonth] = useState(getCurrentMonth)

  const { revenue, fetchDashboard } = useOwnerStore()
  const { todayRating, fetchTodayRating, applyRatingUpdate } = useKombatStore()
  const { branchPvr, fetchBranchPvr, fetchThresholds } = usePvrStore()

  const branches = useMemo(() => revenue?.branches ?? [], [revenue])
  const isCurrentMonth = pvrMonth === getCurrentMonth()

  useEffect(() => {
    if (!revenue) fetchDashboard()
  }, [revenue, fetchDashboard])

  if (branches.length > 0 && !selectedBranchId) {
    setSelectedBranchId(branches[0].branch_id)
  }

  useEffect(() => {
    if (!selectedBranchId) return
    if (tab === 'kombat') {
      fetchTodayRating(selectedBranchId)
    } else {
      fetchBranchPvr(selectedBranchId, pvrMonth)
      fetchThresholds()
    }
  }, [selectedBranchId, tab, pvrMonth, fetchTodayRating, fetchBranchPvr, fetchThresholds])

  const handleWSMessage = useCallback(
    (message: WSMessage) => {
      if (message.type === 'rating_update') {
        const data = message.data as { branch_id?: string; ratings?: RatingEntry[] }
        if (data.branch_id === selectedBranchId && data.ratings) {
          applyRatingUpdate(data.ratings)
        }
      }
    },
    [selectedBranchId, applyRatingUpdate],
  )
  useWebSocket(handleWSMessage)

  return (
    <div className="pb-4 pt-4">
      <div className="flex items-center justify-between px-4">
        <h1 className="bk-heading text-xl">Рейтинг и премии</h1>
        <InfoButton onClick={() => setInfoOpen(true)} />
      </div>

      {/* Tabs */}
      <div className="mx-4 mt-3 flex gap-2">
        {[
          { key: 'kombat' as Tab, label: 'Рейтинг дня' },
          { key: 'pvr' as Tab, label: 'Премии' },
        ].map((t) => (
          <button
            key={t.key}
            type="button"
            className={`flex-1 rounded-lg py-2.5 text-sm font-semibold transition-colors ${
              tab === t.key
                ? 'bg-[var(--bk-gold)] text-[var(--bk-bg-primary)]'
                : 'bg-[var(--bk-bg-elevated)] text-[var(--bk-text-secondary)]'
            }`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Branch selector */}
      <div className="mx-4 mt-3">
        <select
          className="w-full rounded-xl border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-3 py-2.5 text-sm text-[var(--bk-text)]"
          value={selectedBranchId ?? ''}
          onChange={(e) => setSelectedBranchId(e.target.value)}
        >
          {branches.map((b) => (
            <option key={b.branch_id} value={b.branch_id}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      {/* Content */}
      <div className="mx-4 mt-3">
        {tab === 'kombat' &&
          (todayRating ? (
            <div className="bk-card overflow-hidden">
              <div className="flex items-center justify-between px-3 pb-1 pt-3">
                <span className="text-sm font-medium text-[var(--bk-text)]">
                  {todayRating.branch_name}
                </span>
                {todayRating.is_active && (
                  <span className="flex items-center gap-1 text-xs font-bold text-[var(--bk-red)]">
                    <span className="bk-live-pulse inline-block h-1.5 w-1.5 rounded-full bg-[var(--bk-red)]" />
                    LIVE
                  </span>
                )}
              </div>

              {/* Legend */}
              <div className="flex flex-wrap gap-x-3 gap-y-1 px-3 pb-2">
                {SEGMENT_LABELS.map((label, i) => (
                  <span key={label} className="flex items-center gap-1 text-[10px] text-[var(--bk-text-dim)]">
                    <span className={`inline-block h-1.5 w-1.5 rounded-full ${SEGMENT_COLORS[i]}`} />
                    {label}
                  </span>
                ))}
              </div>

              <div className="divide-y divide-[var(--bk-border)]">
                {todayRating.ratings.map((r) => (
                  <RatingRow key={r.barber_id} entry={r} weights={todayRating.weights} />
                ))}
              </div>
              {todayRating.ratings.length === 0 && (
                <p className="p-4 text-center text-sm text-[var(--bk-text-secondary)]">
                  Данных за сегодня нет
                </p>
              )}

              {/* Explanation */}
              <div className="border-t border-[var(--bk-border)] px-3 py-2">
                <p className="text-[10px] leading-relaxed text-[var(--bk-text-dim)]">
                  Баллы (макс. 100) складываются из 5 показателей. Лучший по каждому получает максимум, остальные — пропорционально.
                </p>
              </div>

              {/* Prize fund */}
              <div className="flex justify-center gap-4 border-t border-[var(--bk-border)] px-3 py-2">
                <span className="text-[10px] text-[var(--bk-text-dim)]">Призы за день:</span>
                {[
                  { rank: 1, v: todayRating.prize_fund.gold },
                  { rank: 2, v: todayRating.prize_fund.silver },
                  { rank: 3, v: todayRating.prize_fund.bronze },
                ].map((p) => (
                  <span
                    key={p.rank}
                    className="flex items-center gap-1.5 text-xs tabular-nums text-[var(--bk-text-secondary)]"
                  >
                    <MedalBadge rank={p.rank} size={20} />
                    {formatMoney(p.v)}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <LoadingSkeleton lines={6} />
          ))}

        {tab === 'pvr' &&
          (branchPvr ? (
            <div className="bk-card overflow-hidden">
              <div className="px-3 pb-1 pt-3">
                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    className="flex h-7 w-7 items-center justify-center rounded-full text-[var(--bk-text-secondary)] active:bg-[var(--bk-bg-elevated)]"
                    onClick={() => setPvrMonth((m) => shiftMonth(m, -1))}
                  >
                    <IconArrowLeft size={16} />
                  </button>
                  <span className="text-sm font-medium text-[var(--bk-text)]">
                    {formatMonthLabel(pvrMonth)}
                  </span>
                  <button
                    type="button"
                    className="flex h-7 w-7 items-center justify-center rounded-full text-[var(--bk-text-secondary)] active:bg-[var(--bk-bg-elevated)] disabled:opacity-30"
                    disabled={isCurrentMonth}
                    onClick={() => setPvrMonth((m) => shiftMonth(m, 1))}
                  >
                    <IconArrowRight size={16} />
                  </button>
                </div>
                <p className="mt-0.5 text-[10px] leading-relaxed text-[var(--bk-text-dim)]">
                  Накопительная выручка каждого барбера с 1-го числа. При достижении порога начисляется премия.
                </p>
              </div>
              <div className="divide-y divide-[var(--bk-border)]">
                {[...branchPvr.barbers]
                  .sort((a, b) => b.monthly_rating_score - a.monthly_rating_score)
                  .map((b) => (
                    <PVRRow
                      key={b.barber_id}
                      barber={b}
                      weights={todayRating?.weights ?? null}
                    />
                  ))}
              </div>
              {branchPvr.barbers.length === 0 && (
                <p className="p-4 text-center text-sm text-[var(--bk-text-secondary)]">
                  Нет данных по премиям
                </p>
              )}
            </div>
          ) : (
            <LoadingSkeleton lines={6} />
          ))}
      </div>

      <InfoSheet
        open={infoOpen}
        onClose={() => setInfoOpen(false)}
        title={tab === 'kombat' ? 'Как работает рейтинг' : 'Как работают премии'}
      >
        {tab === 'kombat' ? (
          <>
            <InfoSection title="Система баллов">
              Каждый рабочий день барберы соревнуются по 5 показателям. Лучший по каждому
              получает максимальный балл, остальные — пропорционально. Итоговый балл (макс.
              100) складывается из всех показателей.
            </InfoSection>
            <InfoSection title="Показатели">
              <InfoMetricRow
                color="bg-[var(--bk-score-revenue)]"
                label="Выручка"
                weight={40}
                description="Общая выручка за день (без товаров)"
              />
              <InfoMetricRow
                color="bg-[var(--bk-score-cs)]"
                label="Средний чек"
                weight={25}
                description="Средняя сумма визита"
              />
              <InfoMetricRow
                color="bg-[var(--bk-score-products)]"
                label="Товары"
                weight={15}
                description="Количество проданных товаров"
              />
              <InfoMetricRow
                color="bg-[var(--bk-score-extras)]"
                label="Доп. услуги"
                weight={10}
                description="Количество дополнительных услуг"
              />
              <InfoMetricRow
                color="bg-[var(--bk-score-reviews)]"
                label="Отзывы"
                weight={10}
                description="Средняя оценка отзывов за день"
              />
            </InfoSection>
            <InfoSection title="Призы">
              По итогам дня три лучших барбера получают денежные призы: золото, серебро
              и бронза. Размер призового фонда настраивается администратором.
            </InfoSection>
          </>
        ) : (
          <>
            <InfoSection title="Накопительная выручка">
              Система отслеживает общую выручку каждого барбера с 1-го числа месяца.
              При достижении установленных порогов начисляется премия.
            </InfoSection>
            <InfoSection title="Пороги">
              Администратор задаёт пороги выручки и размер премии за каждый порог.
              Барбер может достичь нескольких порогов за месяц — премии суммируются.
            </InfoSection>
            <InfoSection title="Сброс">
              Накопительная выручка обнуляется 1-го числа каждого месяца. Премии
              начисляются заново.
            </InfoSection>
          </>
        )}
      </InfoSheet>
    </div>
  )
}
