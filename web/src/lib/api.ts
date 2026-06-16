export type HealthResponse = {
  status: string
  db_path: string
}

export type DashboardSummary = {
  server: string
  recent_window_hours: number
  min_discount: number
  listings_recent_count: number
  deals_recent_count: number
  krono_latest: {
    server: string
    price_pp: number | null
    source: string | null
    confidence: string | null
    last_refresh_at: string | null
  }
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

export type ItemSearchResult = {
  item_id: number
  name: string
  icon_url: string | null
  slot: string | null
  classes: string | null
  flags: string | null
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

export async function fetchDealsPreview(
  server: string,
  fetcher: Fetcher = fetch
): Promise<DealPreview[]> {
  return fetchJson<DealPreview[]>(
    buildApiPath("/api/deals", {
      server,
      limit: 5,
      resolved_only: true,
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

export async function fetchSettingsHealth(
  server: string,
  fetcher: Fetcher = fetch
): Promise<HealthResponse> {
  return fetchJson<HealthResponse>(
    buildApiPath(HEALTH_PATH, {
      server,
    }),
    fetcher
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

async function fetchJson<T>(path: string, fetcher: Fetcher = fetch): Promise<T> {
  const response = await fetcher(`${API_BASE_URL}${path}`, {
    headers: {
      Accept: "application/json",
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, `GET ${path} failed with ${response.status}`)
  }

  return (await response.json()) as T
}
