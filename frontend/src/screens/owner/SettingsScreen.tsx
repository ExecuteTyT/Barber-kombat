import { useEffect, useState } from 'react'

import {
  MedalBadge,
  IconArrowLeft,
  IconChevronRight,
  IconCheck,
  IconX,
  IconPlus,
} from '../../components/Icons'
import LoadingSkeleton from '../../components/LoadingSkeleton'
import { useOwnerStore } from '../../stores/ownerStore'
import type {
  RatingWeightsConfig,
  PVRThresholdsConfig,
  PVRThreshold,
  PlanNetworkEntry,
  UserConfig,
  UserRole,
} from '../../types'

function formatMoney(kopecks: number): string {
  const rubles = Math.round(kopecks / 100)
  return rubles.toLocaleString('ru-RU') + '\u{00A0}\u{20BD}'
}

type Section = 'kombat' | 'pvr' | 'plans' | 'branches' | 'staff' | 'notifications'

const SECTIONS: { key: Section; label: string }[] = [
  { key: 'kombat', label: 'Barber Kombat' },
  { key: 'pvr', label: 'ПВР' },
  { key: 'plans', label: 'Планы' },
  { key: 'branches', label: 'Филиалы' },
  { key: 'staff', label: 'Сотрудники' },
  { key: 'notifications', label: 'Уведомления' },
]

function WeightSlider({
  label,
  value,
  onChange,
}: {
  label: string
  value: number
  onChange: (v: number) => void
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-20 text-sm text-[var(--bk-text)]">{label}</span>
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="flex-1"
      />
      <span className="w-10 text-right text-sm font-bold tabular-nums text-[var(--bk-gold)]">
        {value}%
      </span>
    </div>
  )
}

function KombatSection() {
  const { ratingWeights, settingsSaving, fetchRatingWeights, saveRatingWeights } = useOwnerStore()

  const [draft, setDraft] = useState<RatingWeightsConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [prevWeights, setPrevWeights] = useState<RatingWeightsConfig | null>(null)

  useEffect(() => {
    fetchRatingWeights()
  }, [fetchRatingWeights])

  if (ratingWeights && ratingWeights !== prevWeights) {
    setPrevWeights(ratingWeights)
    setDraft({ ...ratingWeights })
  }

  if (!draft) return <LoadingSkeleton lines={5} />

  const total =
    draft.revenue_weight +
    draft.cs_weight +
    draft.products_weight +
    draft.extras_weight +
    draft.reviews_weight

  const handleSave = async () => {
    if (total !== 100) {
      setError(`Сумма весов должна быть 100%, сейчас ${total}%`)
      return
    }
    setError(null)
    const ok = await saveRatingWeights(draft)
    if (!ok) setError('Ошибка сохранения')
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-[var(--bk-text)]">Веса рейтинга (сумма = 100%)</p>
      <WeightSlider
        label="Выручка"
        value={draft.revenue_weight}
        onChange={(v) => setDraft({ ...draft, revenue_weight: v })}
      />
      <WeightSlider
        label="ЧС"
        value={draft.cs_weight}
        onChange={(v) => setDraft({ ...draft, cs_weight: v })}
      />
      <WeightSlider
        label="Товары"
        value={draft.products_weight}
        onChange={(v) => setDraft({ ...draft, products_weight: v })}
      />
      <WeightSlider
        label="Допы"
        value={draft.extras_weight}
        onChange={(v) => setDraft({ ...draft, extras_weight: v })}
      />
      <WeightSlider
        label="Отзывы"
        value={draft.reviews_weight}
        onChange={(v) => setDraft({ ...draft, reviews_weight: v })}
      />
      <p
        className={`text-sm font-bold ${total === 100 ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}`}
      >
        Итого: {total}%
      </p>

      <p className="mt-2 text-sm font-medium text-[var(--bk-text)]">Призовой фонд (%)</p>
      <div className="grid grid-cols-3 gap-2">
        {(['prize_gold_pct', 'prize_silver_pct', 'prize_bronze_pct'] as const).map((key, i) => (
          <div key={key}>
            <label className="flex items-center gap-1 text-xs text-[var(--bk-text-secondary)]">
              <MedalBadge rank={i + 1} size={16} /> место
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="1"
              className="mt-1 w-full rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-2 py-1.5 text-sm text-[var(--bk-text)]"
              value={draft[key]}
              onChange={(e) => setDraft({ ...draft, [key]: Number(e.target.value) })}
            />
          </div>
        ))}
      </div>

      {error && <p className="text-sm text-[var(--bk-red)]">{error}</p>}
      <button
        type="button"
        className="w-full rounded-xl bg-[var(--bk-gold)] py-2.5 text-sm font-semibold text-[var(--bk-bg-primary)] disabled:opacity-50"
        disabled={settingsSaving}
        onClick={handleSave}
      >
        {settingsSaving ? 'Сохранение...' : 'Сохранить'}
      </button>
    </div>
  )
}

function PVRSection() {
  const { pvrThresholds, settingsSaving, fetchPvrThresholds, savePvrThresholds } = useOwnerStore()

  const [draft, setDraft] = useState<PVRThresholdsConfig | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [prevThresholds, setPrevThresholds] = useState<PVRThresholdsConfig | null>(null)

  useEffect(() => {
    fetchPvrThresholds()
  }, [fetchPvrThresholds])

  if (pvrThresholds && pvrThresholds !== prevThresholds) {
    setPrevThresholds(pvrThresholds)
    setDraft({ ...pvrThresholds, thresholds: [...pvrThresholds.thresholds] })
  }

  if (!draft) return <LoadingSkeleton lines={4} />

  const updateThreshold = (idx: number, field: keyof PVRThreshold, value: number) => {
    const updated = [...draft.thresholds]
    updated[idx] = { ...updated[idx], [field]: value }
    setDraft({ ...draft, thresholds: updated })
  }

  const addThreshold = () => {
    const last = draft.thresholds[draft.thresholds.length - 1]
    const newAmount = last ? last.amount + 10000000 : 30000000
    const newBonus = last ? last.bonus + 100000 : 100000
    setDraft({
      ...draft,
      thresholds: [...draft.thresholds, { amount: newAmount, bonus: newBonus }],
    })
  }

  const removeThreshold = (idx: number) => {
    if (draft.thresholds.length <= 1) return
    setDraft({ ...draft, thresholds: draft.thresholds.filter((_, i) => i !== idx) })
  }

  const handleSave = async () => {
    setError(null)
    const ok = await savePvrThresholds(draft)
    if (!ok) setError('Ошибка сохранения')
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-[var(--bk-text)]">Пороги</p>
      {draft.thresholds.map((t, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            type="number"
            placeholder="Сумма"
            className="flex-1 rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-2 py-1.5 text-sm text-[var(--bk-text)]"
            value={t.amount / 100}
            onChange={(e) => updateThreshold(i, 'amount', Number(e.target.value) * 100)}
          />
          <span className="text-xs text-[var(--bk-text-dim)]">
            <IconArrowLeft size={14} className="rotate-180" />
          </span>
          <input
            type="number"
            placeholder="Премия"
            className="w-24 rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-2 py-1.5 text-sm text-[var(--bk-text)]"
            value={t.bonus / 100}
            onChange={(e) => updateThreshold(i, 'bonus', Number(e.target.value) * 100)}
          />
          <button
            type="button"
            className="text-[var(--bk-red)] disabled:opacity-30"
            disabled={draft.thresholds.length <= 1}
            onClick={() => removeThreshold(i)}
          >
            <IconX size={16} />
          </button>
        </div>
      ))}
      <button
        type="button"
        className="flex items-center gap-1 text-sm text-[var(--bk-gold)]"
        onClick={addThreshold}
      >
        <IconPlus size={14} /> Добавить порог
      </button>

      <div className="flex gap-4">
        <label className="flex items-center gap-2 text-sm text-[var(--bk-text)]">
          <input
            type="checkbox"
            checked={draft.count_products}
            onChange={(e) => setDraft({ ...draft, count_products: e.target.checked })}
          />
          Считать товары
        </label>
        <label className="flex items-center gap-2 text-sm text-[var(--bk-text)]">
          <input
            type="checkbox"
            checked={draft.count_certificates}
            onChange={(e) => setDraft({ ...draft, count_certificates: e.target.checked })}
          />
          Считать сертификаты
        </label>
      </div>

      {error && <p className="text-sm text-[var(--bk-red)]">{error}</p>}
      <button
        type="button"
        className="w-full rounded-xl bg-[var(--bk-gold)] py-2.5 text-sm font-semibold text-[var(--bk-bg-primary)] disabled:opacity-50"
        disabled={settingsSaving}
        onClick={handleSave}
      >
        {settingsSaving ? 'Сохранение...' : 'Сохранить'}
      </button>
    </div>
  )
}

function PlansSection() {
  const { plans, settingsSaving, fetchPlans, savePlan } = useOwnerStore()
  const [editingPlan, setEditingPlan] = useState<{ branchId: string; value: string } | null>(null)

  useEffect(() => {
    fetchPlans()
  }, [fetchPlans])

  if (!plans) return <LoadingSkeleton lines={4} />

  const handleSave = async (entry: PlanNetworkEntry) => {
    if (!editingPlan) return
    const amount = Math.round(Number(editingPlan.value) * 100)
    if (amount <= 0) return
    await savePlan(entry.branch_id, plans.month + '-01', amount)
    setEditingPlan(null)
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-[var(--bk-text-secondary)]">
        Период: {plans.month} | Всего: {plans.total_percentage.toFixed(0)}%
      </p>
      {plans.plans.map((p) => (
        <div key={p.branch_id} className="bk-card p-3">
          <div className="flex items-baseline justify-between">
            <span className="font-medium text-[var(--bk-text)]">{p.branch_name}</span>
            <span className="text-sm tabular-nums text-[var(--bk-gold)]">
              {p.percentage.toFixed(0)}%
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-[var(--bk-text-secondary)]">План:</span>
            {editingPlan?.branchId === p.branch_id ? (
              <div className="flex flex-1 items-center gap-1">
                <input
                  type="number"
                  className="flex-1 rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-primary)] px-2 py-1 text-sm text-[var(--bk-text)]"
                  value={editingPlan.value}
                  onChange={(e) => setEditingPlan({ ...editingPlan, value: e.target.value })}
                  autoFocus
                />
                <button
                  type="button"
                  className="rounded bg-[var(--bk-gold)] px-2 py-1 text-xs text-[var(--bk-bg-primary)] disabled:opacity-50"
                  disabled={settingsSaving}
                  onClick={() => handleSave(p)}
                >
                  <IconCheck size={14} />
                </button>
                <button
                  type="button"
                  className="text-[var(--bk-text-dim)]"
                  onClick={() => setEditingPlan(null)}
                >
                  <IconX size={14} />
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="text-sm font-medium text-[var(--bk-gold)]"
                onClick={() =>
                  setEditingPlan({
                    branchId: p.branch_id,
                    value: String(p.target_amount / 100),
                  })
                }
              >
                {formatMoney(p.target_amount)}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function BranchesSection() {
  const { branches, fetchBranches } = useOwnerStore()

  useEffect(() => {
    fetchBranches()
  }, [fetchBranches])

  if (branches.length === 0) return <LoadingSkeleton lines={3} />

  return (
    <div className="space-y-2">
      {branches.map((b) => (
        <div key={b.id} className="bk-card p-3">
          <div className="flex items-center justify-between">
            <span className="font-medium text-[var(--bk-text)]">{b.name}</span>
            <span
              className={`text-xs font-semibold ${b.is_active ? 'text-[var(--bk-green)]' : 'text-[var(--bk-red)]'}`}
            >
              {b.is_active ? 'Активен' : 'Неактивен'}
            </span>
          </div>
          {b.address && <p className="mt-1 text-xs text-[var(--bk-text-secondary)]">{b.address}</p>}
          <div className="mt-1 flex gap-3 text-xs text-[var(--bk-text-dim)]">
            {b.yclients_company_id && <span>YClients: {b.yclients_company_id}</span>}
            {b.telegram_group_id && <span>TG: {b.telegram_group_id}</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function StaffSection() {
  const { users, branches, fetchUsers, fetchBranches, saveUser, settingsSaving } = useOwnerStore()
  const [branchFilter, setBranchFilter] = useState<string>('')

  useEffect(() => {
    fetchUsers(branchFilter || undefined)
    if (branches.length === 0) fetchBranches()
  }, [branchFilter, fetchUsers, branches.length, fetchBranches])

  const ROLE_LABELS: Record<UserRole, string> = {
    owner: 'Владелец',
    manager: 'Управляющий',
    chef: 'Шеф-барбер',
    barber: 'Барбер',
    admin: 'Администратор',
  }

  const handleRoleChange = async (user: UserConfig, role: UserRole) => {
    await saveUser(user.id, { role } as Partial<UserConfig>)
  }

  return (
    <div className="space-y-3">
      <select
        className="w-full rounded-xl border border-[var(--bk-border)] bg-[var(--bk-bg-input)] px-3 py-2 text-sm text-[var(--bk-text)]"
        value={branchFilter}
        onChange={(e) => setBranchFilter(e.target.value)}
      >
        <option value="">Все филиалы</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>

      {users.map((u) => (
        <div key={u.id} className="bk-card p-3">
          <div className="flex items-center justify-between">
            <span className="font-medium text-[var(--bk-text)]">{u.name}</span>
            {!u.is_active && <span className="text-xs text-[var(--bk-red)]">Неактивен</span>}
          </div>
          <div className="mt-2 flex items-center gap-2">
            <select
              className="rounded-lg border border-[var(--bk-border)] bg-[var(--bk-bg-primary)] px-2 py-1 text-xs text-[var(--bk-text)]"
              value={u.role}
              disabled={settingsSaving}
              onChange={(e) => handleRoleChange(u, e.target.value as UserRole)}
            >
              {Object.entries(ROLE_LABELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            {u.grade && (
              <span className="text-xs text-[var(--bk-text-secondary)]">Грейд: {u.grade}</span>
            )}
            {u.haircut_price !== null && (
              <span className="text-xs text-[var(--bk-text-secondary)]">
                {formatMoney(u.haircut_price)}
              </span>
            )}
          </div>
        </div>
      ))}
      {users.length === 0 && (
        <p className="py-4 text-center text-sm text-[var(--bk-text-secondary)]">
          Сотрудники не найдены
        </p>
      )}
    </div>
  )
}

function NotificationsSection() {
  const { notifications, fetchNotifications } = useOwnerStore()

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  if (notifications.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-[var(--bk-text-secondary)]">
        Уведомления не настроены
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {notifications.map((n) => (
        <div key={n.id} className="bk-card flex items-center justify-between p-3">
          <div>
            <p className="text-sm font-medium text-[var(--bk-text)]">{n.notification_type}</p>
            <p className="text-xs text-[var(--bk-text-dim)]">
              Chat: {n.telegram_chat_id}
              {n.schedule_time && ` \u{2022} ${n.schedule_time}`}
            </p>
          </div>
          <span
            className={`text-xs font-semibold ${n.is_enabled ? 'text-[var(--bk-green)]' : 'text-[var(--bk-text-dim)]'}`}
          >
            {n.is_enabled ? 'Вкл' : 'Выкл'}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function SettingsScreen() {
  const [activeSection, setActiveSection] = useState<Section | null>(null)

  if (!activeSection) {
    return (
      <div className="pb-4 pt-4">
        <h1 className="bk-heading px-4 text-xl">Настройки</h1>
        <div className="mx-4 mt-4 space-y-2">
          {SECTIONS.map((s, i) => (
            <button
              key={s.key}
              type="button"
              className="bk-card bk-fade-up flex w-full items-center justify-between px-4 py-3.5 text-left transition-all active:scale-[0.98]"
              style={{ animationDelay: `${i * 50}ms` }}
              onClick={() => setActiveSection(s.key)}
            >
              <span className="font-medium text-[var(--bk-text)]">{s.label}</span>
              <IconChevronRight size={18} className="text-[var(--bk-text-dim)]" />
            </button>
          ))}
        </div>
      </div>
    )
  }

  const sectionLabel = SECTIONS.find((s) => s.key === activeSection)?.label

  return (
    <div className="pb-4 pt-4">
      <div className="flex items-center gap-2 px-4">
        <button
          type="button"
          className="flex items-center gap-1 text-sm text-[var(--bk-gold)]"
          onClick={() => setActiveSection(null)}
        >
          <IconArrowLeft size={18} />
          Назад
        </button>
        <h1 className="bk-heading text-lg">{sectionLabel}</h1>
      </div>

      <div className="mx-4 mt-4">
        {activeSection === 'kombat' && <KombatSection />}
        {activeSection === 'pvr' && <PVRSection />}
        {activeSection === 'plans' && <PlansSection />}
        {activeSection === 'branches' && <BranchesSection />}
        {activeSection === 'staff' && <StaffSection />}
        {activeSection === 'notifications' && <NotificationsSection />}
      </div>
    </div>
  )
}
