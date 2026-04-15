export type UserRole = 'owner' | 'barber' | 'admin'

export interface User {
  id: string
  name: string
  role: UserRole
  branch_id: string | null
  organization_id: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface MeResponse {
  id: string
  telegram_id: number
  name: string
  role: UserRole
  branch_id: string | null
  branch_name: string | null
  organization_id: string
  grade: string | null
  haircut_price: number | null
}

export interface TabItem {
  path: string
  label: string
  icon: import('react').ReactNode
  /** Additional path prefixes that should also mark this tab as active */
  alsoActiveFor?: string[]
}

// --- Kombat types ---

export interface RatingEntry {
  barber_id: string
  name: string
  rank: number
  total_score: number
  revenue: number
  revenue_score: number
  cs_value: number
  cs_score: number
  products_count: number
  products_score: number
  extras_count: number
  extras_score: number
  reviews_avg: number | null
  reviews_score: number
}

export interface PrizeFund {
  gold: number
  silver: number
  bronze: number
}

export interface PlanProgress {
  target: number
  current: number
  percentage: number
  forecast: number | null
  required_daily: number
}

export interface RatingWeights {
  revenue: number
  cs: number
  products: number
  extras: number
  reviews: number
}

export interface TodayRatingResponse {
  branch_id: string
  branch_name: string
  date: string
  is_active: boolean
  ratings: RatingEntry[]
  prize_fund: PrizeFund
  plan: PlanProgress | null
  weights: RatingWeights
}

export interface StandingEntry {
  barber_id: string
  name: string
  wins: number
  avg_score: number
}

export interface StandingsResponse {
  branch_id: string
  month: string
  standings: StandingEntry[]
}

export interface DailyScoreEntry {
  date: string
  score: number
  rank: number
  revenue: number
}

export interface BarberStatsResponse {
  barber_id: string
  name: string
  month: string
  wins: number
  avg_score: number
  total_revenue: number
  avg_revenue_per_day: number
  avg_cs: number
  total_products: number
  total_extras: number
  avg_review: number | null
  daily_scores: DailyScoreEntry[]
}

// --- PVR types (rating-based) ---

export interface PVRThreshold {
  score: number
  bonus: number
}

export interface ThresholdReached {
  score: number
  reached_at: string
}

export interface MetricBreakdown {
  revenue_score: number
  cs_score: number
  products_score: number
  extras_score: number
  reviews_score: number
}

export interface BarberPVRResponse {
  barber_id: string
  name: string
  cumulative_revenue: number
  current_threshold: number | null
  bonus_amount: number
  next_threshold: number | null
  remaining_to_next: number | null
  thresholds_reached: ThresholdReached[]
  monthly_rating_score: number
  metric_breakdown: MetricBreakdown
  working_days: number
  min_visits_required: number
}

export interface ThresholdsResponse {
  thresholds: PVRThreshold[]
  count_products: boolean
  count_certificates: boolean
  min_visits_per_month: number
}

export interface PVRPreviewEntry {
  barber_id: string
  name: string
  monthly_rating_score: number
  working_days: number
  current_threshold: number | null
  bonus_amount: number
  revenue: number
}

export interface PVRPreviewResponse {
  month: string
  total_bonus_fund: number
  barbers: PVRPreviewEntry[]
}

// --- Reviews types ---

export type ReviewStatus = 'new' | 'in_progress' | 'processed'

export interface ReviewResponse {
  id: string
  branch_id: string
  barber_id: string
  barber_name: string
  visit_id: string | null
  client_id: string | null
  client_name: string | null
  client_phone: string | null
  rating: number
  comment: string | null
  source: string
  status: ReviewStatus
  processed_by: string | null
  processed_comment: string | null
  processed_at: string | null
  created_at: string
}

export interface ReviewListResponse {
  reviews: ReviewResponse[]
  total: number
  page: number
  per_page: number
}

export interface AlarumResponse {
  reviews: ReviewResponse[]
  total: number
}

export interface BranchPVRResponse {
  branch_id: string
  month: string
  barbers: BarberPVRResponse[]
}

// --- Reports types ---

export interface BranchRevenue {
  branch_id: string
  name: string
  revenue_today: number
  revenue_mtd: number
  plan_target: number
  plan_percentage: number
  barbers_in_shift: number
  barbers_total: number
}

export interface DailyRevenueReport {
  date: string
  branches: BranchRevenue[]
  network_total_today: number
  network_total_mtd: number
}

export interface DailyDataPoint {
  day: number
  amount: number
}

export interface MonthCumulative {
  name: string
  daily_cumulative: DailyDataPoint[]
}

export interface DayToDayReport {
  branch_id: string | null
  period_end: string
  current_month: MonthCumulative
  prev_month: MonthCumulative
  prev_prev_month: MonthCumulative
  comparison: { vs_prev: string; vs_prev_prev: string }
}

export interface BranchClients {
  branch_id: string
  name: string
  new_clients_today: number
  returning_clients_today: number
  total_today: number
  new_clients_mtd: number
  returning_clients_mtd: number
  total_mtd: number
  retention_rate: number
  avg_check_new: number
  avg_check_returning: number
  visits_mtd: number
}

export interface ClientsReport {
  date: string
  branches: BranchClients[]
  network_new_mtd: number
  network_returning_mtd: number
  network_total_mtd: number
  network_retention_rate: number
  network_avg_check_new: number
  network_avg_check_returning: number
}

// --- Config types ---

export interface RatingWeightsConfig {
  revenue_weight: number
  cs_weight: number
  products_weight: number
  extras_weight: number
  reviews_weight: number
  prize_gold_pct: number
  prize_silver_pct: number
  prize_bronze_pct: number
  extra_services: string[] | null
}

export interface PVRThresholdsConfig {
  thresholds: PVRThreshold[]
  count_products: boolean
  count_certificates: boolean
  min_visits_per_month: number
}

export interface BranchConfig {
  id: string
  organization_id: string
  name: string
  address: string
  yclients_company_id: number | null
  telegram_group_id: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface BranchListResponse {
  branches: BranchConfig[]
}

export interface UserConfig {
  id: string
  organization_id: string
  branch_id: string | null
  telegram_id: number
  role: UserRole
  name: string
  grade: string | null
  haircut_price: number | null
  yclients_staff_id: number | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserListResponse {
  users: UserConfig[]
}

export interface NotificationConfig {
  id: string
  organization_id: string
  branch_id: string | null
  notification_type: string
  telegram_chat_id: number
  is_enabled: boolean
  schedule_time: string | null
  created_at: string
}

export interface NotificationConfigListResponse {
  notifications: NotificationConfig[]
}

// --- Plans types ---

export interface PlanNetworkEntry {
  branch_id: string
  branch_name: string
  target_amount: number
  current_amount: number
  percentage: number
  forecast_amount: number | null
}

export interface PlanNetworkResponse {
  month: string
  plans: PlanNetworkEntry[]
  total_target: number
  total_current: number
  total_percentage: number
}

// --- Admin types ---

export interface AdminMetricsResponse {
  branch_id: string
  branch_name: string
  date: string
  records_today: number
  products_sold: number
  confirmed_tomorrow: number
  total_tomorrow: number
  filled_birthdays: number
  total_clients: number
}

export interface UnconfirmedRecord {
  record_id: string
  client_name: string
  service_name: string
  datetime: string
  barber_name: string
}

export interface UnfilledBirthday {
  client_id: string
  client_name: string
  phone: string | null
  last_visit: string | null
}

export interface UnprocessedCheck {
  record_id: string
  client_name: string
  barber_name: string
  amount: number
  datetime: string
  status: string
}

export interface AdminTasksResponse {
  branch_id: string
  date: string
  unconfirmed_records: UnconfirmedRecord[]
  unfilled_birthdays: UnfilledBirthday[]
  unprocessed_checks: UnprocessedCheck[]
}

export interface AdminDayResult {
  date: string
  records_count: number
  products_sold: number
  revenue: number
  confirmed_rate: number
}

export interface AdminHistoryResponse {
  branch_id: string
  month: string
  days: AdminDayResult[]
}

// --- Branch Analytics types ---

export interface TopBarber {
  barber_id: string
  name: string
  revenue: number
  avg_score: number
  wins: number
  days_worked: number
}

export interface BranchAnalytics {
  branch_id: string
  branch_name: string
  date: string
  revenue_today: number
  revenue_mtd: number
  plan_target: number
  plan_percentage: number
  avg_check_today: number
  avg_check_mtd: number
  visits_today: number
  visits_mtd: number
  clients_today: number
  new_clients_mtd: number
  returning_clients_mtd: number
  total_clients_mtd: number
  barbers_in_shift: number
  barbers_total: number
  top_barbers: TopBarber[]
  total_products_mtd: number
  total_extras_mtd: number
  avg_review_score: number | null
}

// --- WebSocket types ---

export type WSEventType = 'rating_update' | 'pvr_threshold' | 'new_review' | 'plan_update'

export interface WSMessage {
  type: WSEventType
  data: Record<string, unknown>
}
