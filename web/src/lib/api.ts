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
  latest_tlp_import: LatestTlpImport | null
  import_runs_error: string | null
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
  }>
  top_discounts: DashboardDealPreview[]
}

export type DashboardDealPreview = {
  listing_id: number
  timestamp: string
  seller: string | null
  item_id: number | null
  item_name: string
  price_raw: string | null
  listing_price_pp: number
  market_price_pp: number
  market_price_source: string | null
  discount_pct: number
  sample_size: number | null
  confidence: string | null
}

export type DealPreview = DashboardDealPreview & {
  item: {
    item_id: number | null
    name: string
  }
  potential_profit_pp: number
  score: number
  deal_score: number
  resolved: boolean
}

export type DealFilters = {
  minDiscount: number
  minPricePp: number
  limit: number
  resolvedOnly: boolean
}

export const DEFAULT_DEAL_FILTERS: DealFilters = {
  minDiscount: 30,
  minPricePp: 0,
  limit: 100,
  resolvedOnly: true,
}

export type ListingPreview = {
  listing_id: number
  timestamp: string
  seller: string | null
  item_id: number | null
  item_name: string
  price_raw: string | null
  price_pp: number | null
  source: string
  confidence: string | null
  resolved: boolean
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
  historyDays?: number
  concurrency?: number
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
  limit: number
}

export const MARKET_LISTING_PAGE_SIZE = 25

export const DEFAULT_MARKET_LISTING_FILTERS: MarketListingFilters = {
  query: "",
  limit: MARKET_LISTING_PAGE_SIZE,
}

export type ItemSearchResult = {
  item_id: number
  name: string
  icon_url: string | null
  slot: string | null
  classes: string | null
  flags: string | null
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

export type ItemDetail = {
  item_id: number
  name: string
  icon_url: string | null
  icon_id: number | null
  item_type: string | null
  slot: string | null
  classes: string | null
  races: string | null
  flags: string | null
  stats: ItemStats
  combat: ItemCombat
  levels: ItemLevels
  effects: ItemTooltipEffect[]
  source_primary: string | null
  last_imported_at: string | null
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
  item: {
    item_id: number | null
    name: string
  }
  listed_item_name: string
}

export type ItemDetailPageData = {
  item: ItemDetail
  price: ItemMarketPrice
  listings: ItemListing[]
  kronoLatest: KronoLatest
}

export type ItemTooltip = {
  item_id: number
  name: string
  icon_url: string | null
  slot: string | null
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
      history_days: options.historyDays,
      concurrency: options.concurrency,
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
      history_days: options.historyDays,
      concurrency: options.concurrency,
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
  return fetchJson<DealPreview[]>(
    buildApiPath("/api/deals", {
      server,
      min_discount: filters.minDiscount,
      min_price_pp: filters.minPricePp,
      limit: filters.limit,
      resolved_only: filters.resolvedOnly,
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
  return fetchJson<ListingPreview[]>(
    buildApiPath("/api/listings/recent", {
      server,
      q: filters.query.trim() || undefined,
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
  fetcher: Fetcher = fetch
): Promise<ItemDetail> {
  return fetchJson<ItemDetail>(`/api/items/${itemId}`, fetcher)
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

  const [item, price, listings, kronoLatest] = await Promise.all([
    fetchItemDetail(itemId, fetcher),
    fetchItemPrices(itemId, server, fetcher),
    fetchItemListings(itemId, server, fetcher),
    fetchKronoLatest(server, fetcher),
  ])

  return { item, price, listings, kronoLatest }
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

