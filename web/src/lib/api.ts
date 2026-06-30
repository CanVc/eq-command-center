export type HealthResponse = {
  status: string
  db_path: string
}

export type LatestTlpImport = {
  import_run_id: number
  source_name: string
  source_url: string | null
  status: string
  items_seen: number
  items_inserted: number
  items_updated: number
  error: string | null
  started_at: string
  finished_at: string | null
}

export type EqLogImportState = {
  log_path: string
  server: string
  file_size: number | null
  file_mtime: number | null
  last_position: number
  updated_at: string
}

export type EqLogSettings = {
  eq_log_path: string | null
  eq_log_exists: boolean | null
  eq_log_import_state: EqLogImportState | null
  log_settings_error: string | null
}

export type SettingsStatusResponse = EqLogSettings & {
  status: string
  db_path: string
  default_server: string
  active_server: string
}

export type TlpInterfaceError = Omit<LatestTlpImport, "import_run_id"> & {
  import_run_id: number | null
  item_id: number
  item_name: string | null
  price_confidence: string | null
  price_source: string | null
  last_refresh_at: string | null
  latest_listing_at: string | null
  active: boolean
  origin: "import_run" | "market_price_marker"
}

export type TlpInterfaceErrorsResponse = {
  server: string
  max_age_minutes: number
  max_age_hours: number
  stale_item_count: number
  latest_tlp_import: LatestTlpImport | null
  active_errors: TlpInterfaceError[]
  active_error_count: number
}

export type LogParseIssue = {
  id: number
  server: string
  log_path: string | null
  timestamp: string | null
  timestamp_raw: string | null
  seller: string | null
  raw_line: string
  reason_code: string
  reason: string
  created_at: string
  last_seen_at: string
  seen_count: number
}

export type LogParseIssuesResponse = {
  server: string
  issues: LogParseIssue[]
  issue_count: number
  limit: number
}

export type InterfacePageData = {
  tlpErrors: TlpInterfaceErrorsResponse
  logParseIssues: LogParseIssuesResponse
}

export type MarkTlpPricesStaleResult = {
  server: string
  affected_count: number
}

export type LogWatcherStatus = {
  running: boolean
  log_path: string | null
  log_exists: boolean | null
  server: string | null
  last_position: number | null
  last_checked_at: string | null
  last_imported_at: string | null
  latest_sale_at: string | null
  lines_read: number
  auction_lines: number
  listings_found: number
  listings_inserted: number
  error: string | null
}

export type InventoryWatcherStatus = {
  running: boolean
  inventory_directory: string | null
  inventory_directory_exists: boolean | null
  last_checked_at: string | null
  last_imported_at: string | null
  files_seen: number
  files_imported: number
  files_skipped: number
  latest_import_id: number | null
  latest_import_character: string | null
  latest_import_server: string | null
  latest_import_file: string | null
  error: string | null
}

export type RuntimeStatus = {
  server: string
  max_age_hours: number
  max_age_minutes: number
  stale_item_count: number
  latest_log_sale_at: string | null
  log_watcher: LogWatcherStatus | null
  inventory_watcher: InventoryWatcherStatus | null
}

export type DashboardSummary = {
  server: string
  recent_window_hours: number
  min_discount: number
  listings_recent_count: number
  deals_recent_count: number
  krono_latest: KronoLatest
  top_seen_items: Array<{
    item_id: number | null
    item_name: string
    seen_count: number
    last_seen_at: string
    sources: ItemSource[]
  }>
  top_discounts: DashboardDealPreview[]
}

export type DashboardDealPreview = {
  listing_id: number
  timestamp: string
  seller: string | null
  item_id: number | null
  item_name: string
  sources: ItemSource[]
  price_raw: string | null
  raw_line: string | null
  listing_price_pp: number
  market_price_pp: number
  market_price_source: string | null
  discount_pct: number
  sample_size: number | null
  confidence: string | null
  item_preference: ItemPreferenceStatus | null
}

export type ListingReviewStatus = "active" | "discarded" | "suspect"
export type ListingReviewStatusFilter = ListingReviewStatus | "all"
export type ItemPreferenceStatus = "wanted" | "ignored"
export type ItemPreferenceStatusUpdate = ItemPreferenceStatus | "neutral"
export type ItemInterestFilter = "tracked" | "wanted" | "ignored" | "all"

export type ItemPreference = {
  preference_id: number | null
  server: string
  preference_key_kind: "item_id" | "name"
  preference_key: string
  item_id: number | null
  item_name: string
  normalized_item_name: string
  status: ItemPreferenceStatus | "neutral"
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export type ListingReview = {
  listing_id: number
  server: string
  status: ListingReviewStatus
  reason_code: string | null
  note: string | null
  created_at: string
  updated_at: string
}

export type ListingReviewUpdate = {
  status: ListingReviewStatus
  reasonCode?: string | null
  note?: string | null
}

export type ListingDiscardRule = {
  rule_id: number
  enabled: boolean
  server: string
  seller: string | null
  item_id: number
  price_currency: string | null
  price_amount: number | null
  price_pp: number | null
  reason_code: string | null
  note: string | null
  source_listing_id: number | null
  created_at: string
  updated_at: string
  disabled_at: string | null
}

export type ListingSimilarReviewResult = {
  listing_id: number
  server: string
  action: "discard_similar" | "restore_similar"
  rule?: ListingDiscardRule
  disabled_rule_count?: number
  disabled_rules?: ListingDiscardRule[]
  matched_count: number
  restored_count?: number
  review: ListingReview
}

export type DealPreview = DashboardDealPreview & {
  item: {
    item_id: number | null
    name: string
    sources: ItemSource[]
  }
  potential_profit_pp: number
  score: number
  deal_score: number
  resolved: boolean
  review_status: ListingReviewStatus
  review_reason_code: string | null
  review_note: string | null
  item_preference: ItemPreferenceStatus | null
}

export type DealSortBy = "item" | "seen_price" | "market_price" | "discount" | "seller" | "date" | "score"
export type DealSortDirection = "asc" | "desc"

export type DealFilters = {
  minDiscount: number
  minPricePp: number
  limit: number
  resolvedOnly: boolean
  includeSuspect: boolean
  seller: string
  item: string
  dateFrom: string
  sortBy: DealSortBy
  sortDir: DealSortDirection
  interestStatus: ItemInterestFilter
}

export const DEFAULT_DEAL_FILTERS: DealFilters = {
  minDiscount: 30,
  minPricePp: 0,
  limit: 100,
  resolvedOnly: true,
  includeSuspect: false,
  seller: "",
  item: "",
  dateFrom: "",
  sortBy: "discount",
  sortDir: "desc",
  interestStatus: "tracked",
}

export type ListingPreview = {
  listing_id: number
  timestamp: string
  seller: string | null
  item: {
    item_id: number | null
    name: string
    sources: ItemSource[]
  }
  item_id: number | null
  item_name: string
  price_raw: string | null
  raw_line: string | null
  price_pp: number | null
  source: string
  confidence: string | null
  resolved: boolean
  review_status: ListingReviewStatus
  review_reason_code: string | null
  review_note: string | null
  item_preference: ItemPreferenceStatus | null
}

export type KronoLatest = {
  server: string
  price_pp: number | null
  source: string | null
  confidence: string | null
  last_refresh_at: string | null
}

export type KronoRefreshResult = {
  server: string
  krono_updated: boolean
  krono_price_pp: number | null
  krono_listings_converted: number
}

export type TlpPriceRefreshResult = {
  server: string
  target_item_ids: number[]
  target_count: number
  limit: number
  max_age_hours: number | null
  max_age_minutes: number | null
  history_days: number
  concurrency: number
  catalog_items_seen: number
  items_upserted: number
  listings_linked: number
  catalog_prices_upserted: number
  history_items_checked: number
  history_prices_upserted: number
  no_price_data: number
  price_refresh_failed: number
  krono_updated: boolean
  krono_price_pp: number | null
  krono_listings_converted: number
}

export type TlpPriceRefreshOptions = {
  limit?: number
  maxAgeHours?: number
  maxAgeMinutes?: number
  historyDays?: number
  concurrency?: number
  refreshKronoWhenEmpty?: boolean
}

export type TlpPriceRefreshJobStatus = {
  job_id: string
  server: string
  status: "queued" | "running" | "completed" | "failed"
  phase: string
  completed: number
  total: number | null
  current_item_id: number | null
  target_item_ids: number[]
  target_count: number
  limit: number
  max_age_hours: number
  max_age_minutes: number
  history_days: number
  concurrency: number
  stats: TlpPriceRefreshResult | null
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export type MarketListingFilters = {
  query: string
  reviewStatus: ListingReviewStatusFilter
  interestStatus: ItemInterestFilter
  limit: number
}

export const MARKET_LISTING_PAGE_SIZE = 25

export const DEFAULT_MARKET_LISTING_FILTERS: MarketListingFilters = {
  query: "",
  reviewStatus: "active",
  interestStatus: "tracked",
  limit: MARKET_LISTING_PAGE_SIZE,
}

export type ItemSearchResult = {
  item_id: number
  name: string
  icon_url: string | null
  slot: string | null
  slot_mask: number | null
  slot_labels: string[]
  slot_display: string | null
  classes: string | null
  flags: string | null
  item_preference: ItemPreferenceStatus | null
}

export type ItemTooltipEffect = {
  effect_slot: number
  trigger_type: string | null
  effect_type_raw: number | null
  spell: {
    spell_id: number | null
    name: string | null
    spell_type: string | null
    target_type: string | null
    skill: string | null
  }
  cast_time_ms: number | null
  required_level: number | null
  effective_level: number | null
  proc_rate: number | null
  charges: number | null
  description: string | null
}

export type ItemStats = {
  ac: number | null
  hp: number | null
  mana: number | null
  endurance: number | null
  hp_regen: number | null
  mana_regen: number | null
  endurance_regen: number | null
  str: number | null
  sta: number | null
  agi: number | null
  dex: number | null
  wis: number | null
  int: number | null
  cha: number | null
  heroic_str: number | null
  heroic_sta: number | null
  heroic_agi: number | null
  heroic_dex: number | null
  heroic_wis: number | null
  heroic_int: number | null
  heroic_cha: number | null
  sv_magic: number | null
  sv_fire: number | null
  sv_cold: number | null
  sv_poison: number | null
  sv_disease: number | null
}

export type ItemCombat = {
  damage: number | null
  delay: number | null
  ratio: number | null
  haste: number | null
}

export type ItemLevels = {
  required_level: number | null
  recommended_level: number | null
}

export type ItemSource = {
  item_id: number
  data_source: string
  source_url: string | null
  external_item_id: string | null
  content_type: string | null
  zone: string | null
  source_area: string | null
  npc_name: string | null
  last_checked_at: string | null
  confidence: string | null
}

export type ItemDetail = {
  item_id: number
  name: string
  icon_url: string | null
  icon_id: number | null
  item_type: string | null
  slot: string | null
  slot_mask: number | null
  slot_labels: string[]
  slot_display: string | null
  classes: string | null
  races: string | null
  flags: string | null
  stats: ItemStats
  combat: ItemCombat
  levels: ItemLevels
  effects: ItemTooltipEffect[]
  sources: ItemSource[]
  source_primary: string | null
  last_imported_at: string | null
  item_preference: ItemPreferenceStatus | null
}

export type ItemMarketPrice = {
  item_id: number
  server: string
  market_price_pp: number | null
  market_price_source: string | null
  median_pp: number | null
  p25_pp: number | null
  p75_pp: number | null
  avg_pp: number | null
  min_pp: number | null
  max_pp: number | null
  sample_size: number | null
  confidence: string | null
  last_refresh_at: string | null
  source: string | null
}

export type ItemListing = ListingPreview & {
  listed_item_name: string
}

export type TlpHistoryPoint = {
  timestamp: string
  price_pp: number
  plat_price: number
  krono_price: number
  krono_price_pp_used: number | null
  seller: string | null
  source: string
}

export type ItemDetailPageData = {
  item: ItemDetail
  price: ItemMarketPrice
  listings: ItemListing[]
  tlpHistory: TlpHistoryPoint[]
  kronoLatest: KronoLatest
}

export type CharacterInventoryArea = "carried" | "bank" | "shared_bank" | "all"

export type CharacterImport = {
  inventory_import_id: number
  character_name: string
  server: string | null
  source_file: string | null
  source_hash: string | null
  source_size_bytes: number | null
  parser_version: string | null
  rows_seen: number
  rows_imported: number
  equipment_items_imported: number
  inventory_items_imported: number
  starter_items_seen: number
  empty_rows_skipped: number
  status: string
  error: string | null
  imported_at: string
  age_seconds: number | null
}

export type CharacterSummary = {
  character_name: string
  name: string
  server: string | null
  character_class: string | null
  level: number | null
  notes: string | null
  created_at: string | null
  updated_at: string | null
  last_imported_at: string | null
  last_import: CharacterImport | null
  freshness: {
    imported: boolean
    last_imported_at: string | null
    age_seconds: number | null
  }
  equipment_item_count: number
  inventory_item_count: number
  inventory_quantity: number
  starter_item_count: number
  distinct_item_count: number
  unenriched_item_count: number
  unpriced_item_count: number
}

export type CharacterItemPrice = {
  market_price_pp: number | null
  market_price_source: string | null
  median_pp: number | null
  p25_pp: number | null
  p75_pp: number | null
  avg_pp: number | null
  min_pp: number | null
  max_pp: number | null
  sample_size: number | null
  confidence: string | null
  last_refresh_at: string | null
  source: string | null
}

export type CharacterInventoryItemDetail = {
  item_id: number | null
  name: string
  raw_item_name: string | null
  imported_name: string | null
  normalized_name: string | null
  icon_url: string | null
  icon_id: number | null
  item_type: string | null
  slot: string | null
  slot_mask: number | null
  slot_labels: string[]
  slot_display: string | null
  classes: string | null
  races: string | null
  flags: string | null
  quantity: number
  stats: ItemStats
  combat: ItemCombat
  levels: ItemLevels
  source_primary: string | null
  last_imported_at: string | null
  enriched: boolean
  enrichment_status: string
  is_starter_item: boolean
  is_no_trade_import: boolean
  is_container?: boolean
  is_augment: boolean
  augment_parent_location: string | null
  has_price: boolean
  price: CharacterItemPrice
}

export type CharacterEquipmentItem = CharacterInventoryItemDetail & {
  raw_location: string | null
}

export type CharacterEquipmentSlot = {
  slot_key: string
  slot: string
  slot_index: number
  label: string
  item: CharacterEquipmentItem | null
}

export type CharacterEquipmentResponse = {
  character_name: string
  server: string | null
  last_import: CharacterImport | null
  slot_order: string[]
  slots: Record<string, CharacterEquipmentSlot>
}

export type CharacterInventoryLocation = {
  inventory_item_id: number
  area: CharacterInventoryArea
  raw_location: string | null
  parent_location: string | null
  location_index: number | null
  location_slot_index: number | null
  quantity: number
  raw_item_name: string | null
  is_container: boolean
  is_starter_item: boolean
  is_augment: boolean
  augment_parent_location: string | null
}

export type CharacterInventoryGroup = {
  item_id: number | null
  item_name: string
  name: string
  quantity: number
  areas: CharacterInventoryArea[]
  area_quantities: Partial<Record<CharacterInventoryArea, number>>
  raw_item_names: string[]
  is_starter_item: boolean
  is_no_trade_import: boolean
  is_container: boolean
  is_augment: boolean
  has_price: boolean
  enriched: boolean
  enrichment_status: string
  locations: CharacterInventoryLocation[] | null
  item: CharacterInventoryItemDetail
}

export type CharacterInventoryResponse = {
  character_name: string
  server: string | null
  area: CharacterInventoryArea
  available_areas: Exclude<CharacterInventoryArea, "all">[]
  include_locations: boolean
  last_import: CharacterImport | null
  item_count: number
  location_count: number
  total_quantity: number
  items: CharacterInventoryGroup[]
}

export type CharacterUpgradeSourceFilter = "owned" | "market" | "all"
export type CharacterUpgradeSource = "owned" | "local_listing" | "market_price"
export type CharacterUpgradeStat =
  | "ac"
  | "hp"
  | "mana"
  | "endurance"
  | "hp_regen"
  | "mana_regen"
  | "endurance_regen"
  | "str"
  | "sta"
  | "agi"
  | "dex"
  | "wis"
  | "int"
  | "cha"
  | "heroic_str"
  | "heroic_sta"
  | "heroic_agi"
  | "heroic_dex"
  | "heroic_wis"
  | "heroic_int"
  | "heroic_cha"
  | "sv_magic"
  | "sv_fire"
  | "sv_cold"
  | "sv_poison"
  | "sv_disease"
  | "resists_total"
  | "base_stats_total"
  | "damage"
  | "delay"
  | "ratio"
  | "haste"

export type CharacterUpgradeFilters = {
  slot?: string | null
  maxPricePp?: number | null
  source?: CharacterUpgradeSourceFilter
  itemType?: string | null
  classFilter?: string | null
  stats?: CharacterUpgradeStat[]
  betterOnly?: boolean
  limit?: number
}

export type CharacterUpgradeItem = {
  item_id: number
  name: string
  normalized_name: string | null
  icon_url: string | null
  icon_id: number | null
  item_type: string | null
  slot: string | null
  slot_mask: number | null
  slot_labels: string[]
  slot_display: string | null
  classes: string | null
  races: string | null
  flags: string | null
  stats: ItemStats
  combat: ItemCombat
  levels: ItemLevels
  sources: ItemSource[]
  source_primary: string | null
  last_imported_at: string | null
  price: CharacterItemPrice
}

export type CharacterUpgradeCurrentItem = {
  item_id: number
  name: string
  stats: ItemStats
  combat: ItemCombat
  price: CharacterItemPrice
}

export type CharacterUpgradeDeltas = {
  ac: number
  hp: number
  mana: number
  endurance: number
  hp_regen: number
  mana_regen: number
  endurance_regen: number
  str: number
  sta: number
  agi: number
  dex: number
  wis: number
  int: number
  cha: number
  heroic_str: number
  heroic_sta: number
  heroic_agi: number
  heroic_dex: number
  heroic_wis: number
  heroic_int: number
  heroic_cha: number
  sv_magic: number
  sv_fire: number
  sv_cold: number
  sv_poison: number
  sv_disease: number
  resists_total: number
  base_stats_total: number
  damage: number
  delay: number
  ratio: number | null
  haste: number
}

export type CharacterUpgradeListing = {
  listing_id: number
  timestamp: string
  seller: string | null
  price_raw: string | null
  price_pp: number | null
}

export type CharacterUpgradeCandidate = {
  slot_key: string
  slot: string
  slot_label: string
  current_item: CharacterUpgradeCurrentItem | null
  candidate: CharacterUpgradeItem
  source: CharacterUpgradeSource
  source_detail: string | null
  quantity: number | null
  areas: Exclude<CharacterInventoryArea, "all">[]
  area_quantities: Partial<Record<Exclude<CharacterInventoryArea, "all">, number>>
  listing: CharacterUpgradeListing | null
  decision_status: InventorySellDecisionStatus | null
  cost_pp: number | null
  market_price_pp: number | null
  price_source: string | null
  confidence: string | null
  deltas: CharacterUpgradeDeltas
  score: number
}

export type CharacterUpgradesResponse = {
  character_name: string
  server: string | null
  character_class: string | null
  stats: CharacterUpgradeStat[]
  better_only: boolean
  source: CharacterUpgradeSourceFilter
  slot: string | null
  item_type: string | null
  class_filter: string | null
  effective_classes: string[] | null
  max_price_pp: number | null
  local_listing_max_age_days: number
  limit: number
  candidate_count: number
  candidates: CharacterUpgradeCandidate[]
}

export type InventorySellDecisionStatus = "keep" | "sell" | "ignore"
export type InventorySellDecisionScope = "character" | "global"
export type InventorySellCandidateCategory = "sellable" | "keep" | "ignored" | "no_drop" | "unpriced" | "excluded"

export type InventorySellDecision = {
  decision_id: number | null
  scope: InventorySellDecisionScope
  status: InventorySellDecisionStatus | null
  notes: string | null
  created_at: string | null
  updated_at: string | null
}

export type InventorySellDecisionRecord = InventorySellDecision & {
  server: string
  scope_key: string
  character_name: string | null
  item_id: number
  item_name: string
  normalized_item_name: string
}

export type InventorySellCandidate = {
  character_name: string
  server: string
  item_id: number
  item_name: string
  name: string
  normalized_item_name: string
  quantity: number
  areas: Exclude<CharacterInventoryArea, "all">[]
  area_quantities: Partial<Record<Exclude<CharacterInventoryArea, "all">, number>>
  location_count: number
  raw_item_names: string[]
  item_type: string | null
  flags: string | null
  source_primary: string | null
  icon_id: number | null
  last_imported_at: string | null
  is_starter_item: boolean
  is_no_trade_import: boolean
  is_no_drop: boolean
  is_container: boolean
  is_consumable: boolean
  is_augment: boolean
  default_exclusion_reasons: string[]
  decision_status: InventorySellDecisionStatus | null
  decision: InventorySellDecision | null
  estimated_unit_price_pp: number | null
  estimated_total_pp: number | null
  price_source: string | null
  price_source_detail: string | null
  confidence: string | null
  price_sample_size: number | null
  price_last_seen_at: string | null
  category: InventorySellCandidateCategory
}

export type InventorySellGlobalItem = {
  server: string
  item_id: number
  item_name: string
  name: string
  normalized_item_name: string
  quantity: number
  characters: Array<{
    character_name: string
    quantity: number
    category: InventorySellCandidateCategory
    decision_status: InventorySellDecisionStatus | null
  }>
  estimated_unit_price_pp: number | null
  estimated_total_pp: number | null
  price_source: string | null
  price_source_detail: string | null
  confidence: string | null
  categories: InventorySellCandidateCategory[]
}

export type InventorySellCandidatesResponse = {
  scope: InventorySellDecisionScope
  character_name: string | null
  server: string | null
  local_listing_max_age_days: number
  item_count: number
  total_quantity: number
  sellable_total_value_pp: number
  categories: Record<InventorySellCandidateCategory, InventorySellCandidate[]>
  items: InventorySellCandidate[]
  global_items: InventorySellGlobalItem[]
}

export type ItemTooltip = {
  item_id: number
  name: string
  icon_url: string | null
  slot: string | null
  slot_mask: number | null
  slot_labels: string[]
  slot_display: string | null
  classes: string | null
  races: string | null
  item_type: string | null
  flags: string | null
  server: string
  ac: number | null
  hp: number | null
  mana: number | null
  endurance: number | null
  hp_regen: number | null
  mana_regen: number | null
  endurance_regen: number | null
  str: number | null
  sta: number | null
  agi: number | null
  dex: number | null
  wis: number | null
  int: number | null
  cha: number | null
  heroic_str: number | null
  heroic_sta: number | null
  heroic_agi: number | null
  heroic_dex: number | null
  heroic_wis: number | null
  heroic_int: number | null
  heroic_cha: number | null
  sv_magic: number | null
  sv_fire: number | null
  sv_cold: number | null
  sv_poison: number | null
  sv_disease: number | null
  damage: number | null
  delay: number | null
  ratio: number | null
  haste: number | null
  required_level: number | null
  recommended_level: number | null
  market_price_pp: number | null
  market_price_source: string | null
  median_pp: number | null
  p25_pp: number | null
  p75_pp: number | null
  avg_pp: number | null
  sample_size: number | null
  confidence: string | null
  last_refresh_at: string | null
  last_seen_pp: number | null
  last_seen_at: string | null
  last_seen_seller: string | null
  last_seen_price_raw: string | null
  effects: ItemTooltipEffect[]
  sources: ItemSource[]
  item_preference: ItemPreferenceStatus | null
}

export type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "")
const HEALTH_PATH = "/api/health"

type QueryValue = string | number | boolean | null | undefined

export async function fetchHealth(fetcher: Fetcher = fetch): Promise<HealthResponse> {
  return fetchJson<HealthResponse>(HEALTH_PATH, fetcher)
}

export async function fetchRuntimeStatus(
  server: string,
  maxAgeMinutes: number,
  fetcher: Fetcher = fetch
): Promise<RuntimeStatus> {
  return fetchJson<RuntimeStatus>(
    buildApiPath("/api/runtime/status", {
      server,
      max_age_minutes: maxAgeMinutes,
    }),
    fetcher
  )
}

export async function fetchDashboardSummary(
  server: string,
  fetcher: Fetcher = fetch
): Promise<DashboardSummary> {
  return fetchJson<DashboardSummary>(
    buildApiPath("/api/dashboard/summary", {
      server,
      top_limit: 5,
    }),
    fetcher
  )
}

export async function fetchKronoLatest(
  server: string,
  fetcher: Fetcher = fetch
): Promise<KronoLatest> {
  return fetchJson<KronoLatest>(
    buildApiPath("/api/krono/latest", {
      server,
    }),
    fetcher
  )
}

export async function refreshKronoPrice(
  server: string,
  fetcher: Fetcher = fetch
): Promise<KronoRefreshResult> {
  return fetchJson<KronoRefreshResult>(
    buildApiPath("/api/krono/refresh", {
      server,
    }),
    fetcher,
    { method: "POST" }
  )
}

export async function refreshTlpPrices(
  server: string,
  options: TlpPriceRefreshOptions = {},
  fetcher: Fetcher = fetch
): Promise<TlpPriceRefreshResult> {
  return fetchJson<TlpPriceRefreshResult>(
    buildApiPath("/api/tlp-prices/refresh", {
      server,
      limit: options.limit,
      max_age_hours: options.maxAgeHours,
      max_age_minutes: options.maxAgeMinutes,
      history_days: options.historyDays,
      concurrency: options.concurrency,
      refresh_krono_when_empty: options.refreshKronoWhenEmpty,
    }),
    fetcher,
    { method: "POST" }
  )
}

export async function startTlpPriceRefreshJob(
  server: string,
  options: TlpPriceRefreshOptions = {},
  fetcher: Fetcher = fetch
): Promise<TlpPriceRefreshJobStatus> {
  return fetchJson<TlpPriceRefreshJobStatus>(
    buildApiPath("/api/tlp-prices/refresh-jobs", {
      server,
      limit: options.limit,
      max_age_hours: options.maxAgeHours,
      max_age_minutes: options.maxAgeMinutes,
      history_days: options.historyDays,
      concurrency: options.concurrency,
      refresh_krono_when_empty: options.refreshKronoWhenEmpty,
    }),
    fetcher,
    { method: "POST" }
  )
}

export async function fetchTlpPriceRefreshJob(
  jobId: string,
  fetcher: Fetcher = fetch
): Promise<TlpPriceRefreshJobStatus> {
  return fetchJson<TlpPriceRefreshJobStatus>(`/api/tlp-prices/refresh-jobs/${jobId}`, fetcher)
}

export async function refreshTlpItemPrice(
  itemId: number,
  server: string,
  options: Pick<TlpPriceRefreshOptions, "historyDays"> = {},
  fetcher: Fetcher = fetch
): Promise<TlpPriceRefreshResult> {
  return fetchJson<TlpPriceRefreshResult>(
    buildApiPath(`/api/tlp-prices/items/${itemId}/refresh`, {
      server,
      history_days: options.historyDays,
    }),
    fetcher,
    { method: "POST" }
  )
}

export async function fetchDealsPreview(
  server: string,
  fetcher: Fetcher = fetch
): Promise<DealPreview[]> {
  return fetchDeals(server, { ...DEFAULT_DEAL_FILTERS, limit: 5 }, fetcher)
}

export async function fetchDeals(
  server: string,
  filters: DealFilters = DEFAULT_DEAL_FILTERS,
  fetcher: Fetcher = fetch
): Promise<DealPreview[]> {
  const interestStatus = filters.interestStatus ?? DEFAULT_DEAL_FILTERS.interestStatus
  const usesDefaultSort = filters.sortBy === DEFAULT_DEAL_FILTERS.sortBy && filters.sortDir === DEFAULT_DEAL_FILTERS.sortDir

  return fetchJson<DealPreview[]>(
    buildApiPath("/api/deals", {
      server,
      min_discount: filters.minDiscount,
      min_price_pp: filters.minPricePp,
      limit: filters.limit,
      resolved_only: filters.resolvedOnly,
      include_suspect: filters.includeSuspect,
      seller: filters.seller?.trim() || undefined,
      item: filters.item?.trim() || undefined,
      date_from: filters.dateFrom?.trim() || undefined,
      interest_status: interestStatus === DEFAULT_DEAL_FILTERS.interestStatus ? undefined : interestStatus,
      sort_by: usesDefaultSort ? undefined : filters.sortBy,
      sort_dir: usesDefaultSort ? undefined : filters.sortDir,
    }),
    fetcher
  )
}

export async function fetchListingsPreview(
  server: string,
  fetcher: Fetcher = fetch
): Promise<ListingPreview[]> {
  return fetchJson<ListingPreview[]>(
    buildApiPath("/api/listings/recent", {
      server,
      limit: 5,
    }),
    fetcher
  )
}

export async function fetchMarketListings(
  server: string,
  filters: MarketListingFilters = DEFAULT_MARKET_LISTING_FILTERS,
  fetcher: Fetcher = fetch
): Promise<ListingPreview[]> {
  const interestStatus = filters.interestStatus ?? DEFAULT_MARKET_LISTING_FILTERS.interestStatus

  return fetchJson<ListingPreview[]>(
    buildApiPath("/api/listings/recent", {
      server,
      q: filters.query.trim() || undefined,
      review_status: filters.reviewStatus,
      interest_status: interestStatus === DEFAULT_MARKET_LISTING_FILTERS.interestStatus ? undefined : interestStatus,
      limit: filters.limit,
    }),
    fetcher
  )
}

export async function fetchItemSearchPreview(
  server: string,
  fetcher: Fetcher = fetch
): Promise<ItemSearchResult[]> {
  return fetchJson<ItemSearchResult[]>(
    buildApiPath("/api/items/search", {
      server,
      q: "stave",
      limit: 5,
    }),
    fetcher
  )
}

export async function fetchItemDetail(
  itemId: number,
  server: string,
  fetcher: Fetcher = fetch
): Promise<ItemDetail> {
  return fetchJson<ItemDetail>(
    buildApiPath(`/api/items/${itemId}`, {
      server,
    }),
    fetcher
  )
}

export async function fetchItemPrices(
  itemId: number,
  server: string,
  fetcher: Fetcher = fetch
): Promise<ItemMarketPrice> {
  return fetchJson<ItemMarketPrice>(
    buildApiPath(`/api/items/${itemId}/prices`, {
      server,
    }),
    fetcher
  )
}

export async function fetchItemListings(
  itemId: number,
  server: string,
  fetcher: Fetcher = fetch
): Promise<ItemListing[]> {
  return fetchJson<ItemListing[]>(
    buildApiPath(`/api/items/${itemId}/listings`, {
      server,
      limit: 100,
    }),
    fetcher
  )
}

export async function fetchTlpItemHistory(
  itemId: number,
  server: string,
  fetcher: Fetcher = fetch
): Promise<TlpHistoryPoint[]> {
  return fetchJson<TlpHistoryPoint[]>(
    buildApiPath(`/api/items/${itemId}/tlp-history`, {
      server,
    }),
    fetcher
  )
}

export async function fetchItemDetailPageData(
  itemId: number,
  server: string,
  fetcher: Fetcher = fetch
): Promise<ItemDetailPageData> {
  try {
    await refreshTlpItemPrice(itemId, server, {}, fetcher)
  } catch (error) {
    console.warn("Unable to refresh TLP item price before loading item detail", error)
  }

  const [item, price, listings, tlpHistory, kronoLatest] = await Promise.all([
    fetchItemDetail(itemId, server, fetcher),
    fetchItemPrices(itemId, server, fetcher),
    fetchItemListings(itemId, server, fetcher),
    fetchTlpItemHistory(itemId, server, fetcher).catch((error) => {
      console.warn("Unable to load full TLP item history", error)
      return []
    }),
    fetchKronoLatest(server, fetcher),
  ])

  return { item, price, listings, tlpHistory, kronoLatest }
}

export async function fetchCharacters(
  server: string,
  fetcher: Fetcher = fetch
): Promise<CharacterSummary[]> {
  return fetchJson<CharacterSummary[]>(
    buildApiPath("/api/characters", {
      server,
    }),
    fetcher
  )
}

export async function fetchCharacterEquipment(
  characterName: string,
  fetcher: Fetcher = fetch
): Promise<CharacterEquipmentResponse> {
  return fetchJson<CharacterEquipmentResponse>(
    `/api/characters/${encodeURIComponent(characterName)}/equipment`,
    fetcher
  )
}

export async function fetchCharacterInventory(
  characterName: string,
  area: CharacterInventoryArea = "all",
  fetcher: Fetcher = fetch
): Promise<CharacterInventoryResponse> {
  return fetchJson<CharacterInventoryResponse>(
    buildApiPath(`/api/characters/${encodeURIComponent(characterName)}/inventory`, {
      area,
    }),
    fetcher
  )
}

export async function fetchCharacterUpgrades(
  characterName: string,
  filters: CharacterUpgradeFilters = {},
  fetcher: Fetcher = fetch
): Promise<CharacterUpgradesResponse> {
  return fetchJson<CharacterUpgradesResponse>(
    buildApiPath(`/api/characters/${encodeURIComponent(characterName)}/upgrades`, {
      slot: filters.slot?.trim() || undefined,
      max_price_pp: filters.maxPricePp,
      source: filters.source,
      item_type: filters.itemType?.trim() || undefined,
      class_filter: filters.classFilter?.trim() || undefined,
      stats: filters.stats && filters.stats.length > 0 ? filters.stats.join(",") : undefined,
      better_only: filters.betterOnly,
      limit: filters.limit,
    }),
    fetcher
  )
}

export async function fetchInventorySellCandidates(
  server: string,
  fetcher: Fetcher = fetch
): Promise<InventorySellCandidatesResponse> {
  return fetchJson<InventorySellCandidatesResponse>(
    buildApiPath("/api/inventory/sell-candidates", {
      server,
    }),
    fetcher
  )
}

export async function fetchCharacterInventorySellCandidates(
  characterName: string,
  fetcher: Fetcher = fetch
): Promise<InventorySellCandidatesResponse> {
  return fetchJson<InventorySellCandidatesResponse>(
    `/api/characters/${encodeURIComponent(characterName)}/sell-candidates`,
    fetcher
  )
}

export async function updateGlobalInventoryItemDecision(
  itemId: number,
  server: string,
  status: InventorySellDecisionStatus,
  notes: string | null = null,
  fetcher: Fetcher = fetch
): Promise<InventorySellDecisionRecord> {
  return fetchJson<InventorySellDecisionRecord>(
    buildApiPath(`/api/inventory/items/${itemId}/decision`, {
      server,
    }),
    fetcher,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status, notes }),
    }
  )
}

export async function clearGlobalInventoryItemDecision(
  itemId: number,
  server: string,
  fetcher: Fetcher = fetch
): Promise<InventorySellDecisionRecord> {
  return fetchJson<InventorySellDecisionRecord>(
    buildApiPath(`/api/inventory/items/${itemId}/decision`, {
      server,
    }),
    fetcher,
    { method: "DELETE" }
  )
}

export async function updateCharacterInventoryItemDecision(
  characterName: string,
  itemId: number,
  status: InventorySellDecisionStatus,
  notes: string | null = null,
  fetcher: Fetcher = fetch
): Promise<InventorySellDecisionRecord> {
  return fetchJson<InventorySellDecisionRecord>(
    `/api/characters/${encodeURIComponent(characterName)}/inventory/items/${itemId}/decision`,
    fetcher,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status, notes }),
    }
  )
}

export async function clearCharacterInventoryItemDecision(
  characterName: string,
  itemId: number,
  fetcher: Fetcher = fetch
): Promise<InventorySellDecisionRecord> {
  return fetchJson<InventorySellDecisionRecord>(
    `/api/characters/${encodeURIComponent(characterName)}/inventory/items/${itemId}/decision`,
    fetcher,
    { method: "DELETE" }
  )
}

export async function fetchItemTooltip(
  {
    itemId,
    name,
    server,
  }: {
    itemId: number | null
    name: string
    server: string
  },
  fetcher: Fetcher = fetch
): Promise<ItemTooltip> {
  if (itemId !== null && itemId !== undefined) {
    return fetchJson<ItemTooltip>(
      buildApiPath(`/api/items/${itemId}/tooltip`, {
        server,
      }),
      fetcher
    )
  }

  return fetchJson<ItemTooltip>(
    buildApiPath("/api/items/tooltip", {
      server,
      name,
    }),
    fetcher
  )
}

export async function fetchItemPreferences(
  server: string,
  status?: ItemPreferenceStatus,
  fetcher: Fetcher = fetch
): Promise<ItemPreference[]> {
  return fetchJson<ItemPreference[]>(
    buildApiPath("/api/items/preferences", {
      server,
      status,
    }),
    fetcher
  )
}

export async function updateItemPreference(
  itemId: number,
  server: string,
  status: ItemPreferenceStatusUpdate,
  notes: string | null = null,
  fetcher: Fetcher = fetch
): Promise<ItemPreference> {
  return fetchJson<ItemPreference>(
    buildApiPath(`/api/items/${itemId}/preference`, {
      server,
    }),
    fetcher,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status, notes }),
    }
  )
}

export async function updateListingItemPreference(
  listingId: number,
  status: ItemPreferenceStatusUpdate,
  notes: string | null = null,
  fetcher: Fetcher = fetch
): Promise<ItemPreference> {
  return fetchJson<ItemPreference>(
    `/api/listings/${listingId}/item-preference`,
    fetcher,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status, notes }),
    }
  )
}

export async function fetchSettingsStatus(
  server: string,
  fetcher: Fetcher = fetch
): Promise<SettingsStatusResponse> {
  return fetchJson<SettingsStatusResponse>(
    buildApiPath("/api/settings/status", {
      server,
    }),
    fetcher
  )
}

export async function fetchTlpInterfaceErrors(
  server: string,
  maxAgeMinutes: number,
  fetcher: Fetcher = fetch
): Promise<TlpInterfaceErrorsResponse> {
  return fetchJson<TlpInterfaceErrorsResponse>(
    buildApiPath("/api/interface/tlp-errors", {
      server,
      max_age_minutes: maxAgeMinutes,
    }),
    fetcher
  )
}

export async function fetchLogParseIssues(
  server: string,
  fetcher: Fetcher = fetch
): Promise<LogParseIssuesResponse> {
  return fetchJson<LogParseIssuesResponse>(
    buildApiPath("/api/interface/log-parse-issues", {
      server,
    }),
    fetcher
  )
}

export async function fetchInterfacePageData(
  server: string,
  maxAgeMinutes: number,
  fetcher: Fetcher = fetch
): Promise<InterfacePageData> {
  const [tlpErrors, logParseIssues] = await Promise.all([
    fetchTlpInterfaceErrors(server, maxAgeMinutes, fetcher),
    fetchLogParseIssues(server, fetcher),
  ])

  return { tlpErrors, logParseIssues }
}

export async function updateListingReview(
  listingId: number,
  review: ListingReviewUpdate,
  fetcher: Fetcher = fetch
): Promise<ListingReview> {
  return fetchJson<ListingReview>(
    `/api/listings/${listingId}/review`,
    fetcher,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: review.status,
        reason_code: review.reasonCode,
        note: review.note,
      }),
    }
  )
}

export async function discardListing(
  listingId: number,
  reasonCode = "manual",
  note: string | null = null,
  fetcher: Fetcher = fetch
): Promise<ListingReview> {
  return updateListingReview(listingId, { status: "discarded", reasonCode, note }, fetcher)
}

export async function restoreListing(
  listingId: number,
  fetcher: Fetcher = fetch
): Promise<ListingReview> {
  return updateListingReview(listingId, { status: "active" }, fetcher)
}

export async function discardSimilarListings(
  listingId: number,
  reasonCode = "manual",
  note: string | null = null,
  fetcher: Fetcher = fetch
): Promise<ListingSimilarReviewResult> {
  return fetchJson<ListingSimilarReviewResult>(
    `/api/listings/${listingId}/discard-similar`,
    fetcher,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason_code: reasonCode, note }),
    }
  )
}

export async function restoreSimilarListings(
  listingId: number,
  fetcher: Fetcher = fetch
): Promise<ListingSimilarReviewResult> {
  return fetchJson<ListingSimilarReviewResult>(
    `/api/listings/${listingId}/restore-similar`,
    fetcher,
    { method: "POST" }
  )
}

export async function markTlpPricesStale(
  server: string,
  fetcher: Fetcher = fetch
): Promise<MarkTlpPricesStaleResult> {
  return fetchJson<MarkTlpPricesStaleResult>(
    buildApiPath("/api/interface/tlp-prices/mark-stale", {
      server,
    }),
    fetcher,
    { method: "POST" }
  )
}

export async function updateEqLogPath(
  server: string,
  logPath: string,
  fetcher: Fetcher = fetch
): Promise<EqLogSettings> {
  return fetchJson<EqLogSettings>(
    buildApiPath("/api/settings/log-path", {
      server,
    }),
    fetcher,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ log_path: logPath }),
    }
  )
}

export async function browseEqLogPath(
  server: string,
  fetcher: Fetcher = fetch
): Promise<EqLogSettings> {
  return fetchJson<EqLogSettings>(
    buildApiPath("/api/settings/log-path/browse", {
      server,
    }),
    fetcher,
    {
      method: "POST",
    }
  )
}

export function buildApiPath(path: string, params: Record<string, QueryValue> = {}): string {
  const search = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      search.set(key, String(value))
    }
  }

  const query = search.toString()
  return query ? `${path}?${query}` : path
}

async function fetchJson<T>(
  path: string,
  fetcher: Fetcher = fetch,
  init: RequestInit = {}
): Promise<T> {
  const method = init.method ?? "GET"
  const response = await fetcher(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...init.headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, await buildApiErrorMessage(response, method, path))
  }

  return (await response.json()) as T
}

async function buildApiErrorMessage(
  response: Response,
  method: string,
  path: string
): Promise<string> {
  const fallbackMessage = `${method} ${path} failed with ${response.status}`

  try {
    const payload = (await response.clone().json()) as { detail?: unknown }
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return `${fallbackMessage}: ${payload.detail}`
    }
  } catch {
    // Ignore non-JSON error bodies.
  }

  return fallbackMessage
}
