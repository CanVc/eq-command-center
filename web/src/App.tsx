import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"

import { AppLayout } from "@/components/app-layout"
import { ItemLink } from "@/components/item-link"
import { ErrorState, LoadingState } from "@/components/page-state"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DEFAULT_DEAL_FILTERS,
  DEFAULT_MARKET_LISTING_FILTERS,
  fetchDashboardSummary,
  fetchDeals,
  fetchItemDetailPageData,
  fetchItemSearchPreview,
  fetchMarketListings,
  fetchSettingsStatus,
  fetchTlpPriceRefreshJob,
  refreshKronoPrice,
  startTlpPriceRefreshJob,
  type DashboardSummary,
  type DealFilters,
  type DealPreview,
  type ItemDetailPageData,
  type ItemSearchResult,
  type ListingPreview,
  type MarketListingFilters,
  type SettingsStatusResponse,
  type TlpPriceRefreshJobStatus,
} from "@/lib/api"
import {
  ensureMageloScript,
  getMageloStatus,
  hideMageloTooltip,
  scanMageloItems,
  subscribeMageloStatus,
  type MageloStatus,
} from "@/lib/magelo"
import {
  activePageIdFromRoute,
  APP_PAGES,
  pathForPage,
  routeFromPath,
  type AppPageDefinition,
  type AppPageId,
  type AppRoute,
} from "@/lib/navigation"
import { readPreferredServer, savePreferredServer } from "@/lib/server-preference"
import {
  TLP_AUTO_REFRESH_INTERVAL_MS,
  formatTlpMaxAgeHours,
  readTlpAutoRefreshEnabled,
  readTlpMaxAgeHours,
  saveTlpAutoRefreshEnabled,
  saveTlpMaxAgeHours,
} from "@/lib/tlp-refresh-preference"
import { formatTime } from "@/lib/format"
import { DashboardPage } from "@/pages/dashboard-page"
import { DealsPage } from "@/pages/deals-page"
import { ItemDetailPage } from "@/pages/item-detail-page"
import { MarketListingsPage } from "@/pages/market-listings-page"
import { SettingsPage } from "@/pages/settings-page"

type PageData =
  | { page: "dashboard"; payload: DashboardSummary }
  | { page: "deals"; payload: DealPreview[] }
  | { page: "market"; payload: ListingPreview[] }
  | { page: "items"; payload: ItemSearchResult[] }
  | { page: "item-detail"; payload: ItemDetailPageData }
  | { page: "settings"; payload: SettingsStatusResponse }

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: PageData; loadedAt: Date }
  | { status: "error"; message: string }

function App() {
  const [activeRoute, setActiveRoute] = useState<AppRoute>(() => getInitialRoute())
  const [server, setServer] = useState(() => readPreferredServer())
  const [tlpMaxAgeHours, setTlpMaxAgeHours] = useState(() => readTlpMaxAgeHours())
  const [tlpAutoRefreshEnabled, setTlpAutoRefreshEnabled] = useState(() => readTlpAutoRefreshEnabled())
  const [dealFilters, setDealFilters] = useState<DealFilters>(DEFAULT_DEAL_FILTERS)
  const [marketListingFilters, setMarketListingFilters] = useState<MarketListingFilters>(
    DEFAULT_MARKET_LISTING_FILTERS
  )
  const [refreshKey, setRefreshKey] = useState(0)
  const [tlpRefreshJob, setTlpRefreshJob] = useState<TlpPriceRefreshJobStatus | null>(null)
  const [progressNow, setProgressNow] = useState(() => Date.now())
  const [mageloStatus, setMageloStatus] = useState<MageloStatus>(() => getMageloStatus())
  const [pageState, setPageState] = useState<PageState>({ status: "loading" })

  const activePage = activePageIdFromRoute(activeRoute)
  const pageDefinition = pageDefinitionForRoute(activeRoute)
  const isTlpRefreshing = isRunningTlpJob(tlpRefreshJob)

  useEffect(() => {
    const handlePopState = () => {
      hideMageloTooltip()
      setPageState({ status: "loading" })
      setActiveRoute(routeFromPath(window.location.pathname))
    }

    window.addEventListener("popstate", handlePopState)

    return () => {
      window.removeEventListener("popstate", handlePopState)
    }
  }, [])

  useEffect(() => {
    const unsubscribe = subscribeMageloStatus(setMageloStatus)
    ensureMageloScript()

    return unsubscribe
  }, [])

  useEffect(() => {
    hideMageloTooltip()
  }, [activeRoute])

  useEffect(() => {
    if (!isTlpRefreshing) {
      return undefined
    }

    const timer = window.setInterval(() => {
      setProgressNow(Date.now())
    }, 1000)

    return () => {
      window.clearInterval(timer)
    }
  }, [isTlpRefreshing])

  useEffect(() => {
    if (pageState.status !== "ready" || mageloStatus !== "loaded") {
      return undefined
    }

    const timer = window.setTimeout(() => {
      scanMageloItems()
    }, 100)

    return () => {
      window.clearTimeout(timer)
    }
  }, [mageloStatus, pageState])

  useEffect(() => {
    let isActive = true

    async function loadPage() {
      try {
        const data = await fetchPageData(activeRoute, server, dealFilters, marketListingFilters)
        if (isActive) {
          setPageState({ status: "ready", data, loadedAt: new Date() })
        }
      } catch (error) {
        if (isActive) {
          setPageState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown API error",
          })
        }
      }
    }

    void loadPage()

    return () => {
      isActive = false
    }
  }, [activeRoute, dealFilters, marketListingFilters, refreshKey, server])

  const navigateTo = useCallback((pageId: AppPageId) => {
    const nextPath = pathForPage(pageId)

    if (pageId === activePage && window.location.pathname === nextPath) {
      return
    }

    hideMageloTooltip()

    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath)
    }

    setPageState({ status: "loading" })
    setActiveRoute({ kind: "page", pageId })
  }, [activePage])

  const changeServer = useCallback((nextServer: string) => {
    const savedServer = savePreferredServer(nextServer)

    if (savedServer === server) {
      return
    }

    setPageState({ status: "loading" })
    setServer(savedServer)
  }, [server])

  const refresh = useCallback(() => {
    setPageState({ status: "loading" })

    async function runRefresh() {
      if (activeRoute.kind === "page" && activeRoute.pageId === "dashboard") {
        try {
          await refreshKronoPrice(server)
        } catch (error) {
          setPageState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown TLP Auctions error",
          })
          return
        }
      }

      setRefreshKey((current) => current + 1)
    }

    void runRefresh()
  }, [activeRoute, server])

  const refreshTlpMarketPrices = useCallback((options: { refreshKronoWhenEmpty?: boolean } = {}) => {
    if (isRunningTlpJob(tlpRefreshJob)) {
      return
    }

    const refreshMaxAgeHours = tlpMaxAgeHours
    const refreshKronoWhenEmpty = options.refreshKronoWhenEmpty ?? true

    async function runTlpRefresh() {
      try {
        let job = await startTlpPriceRefreshJob(server, {
          maxAgeHours: refreshMaxAgeHours,
          refreshKronoWhenEmpty,
        })
        setTlpRefreshJob(job)
        setProgressNow(Date.now())

        while (isRunningTlpJob(job)) {
          await wait(1000)
          job = await fetchTlpPriceRefreshJob(job.job_id)
          setTlpRefreshJob(job)
          setProgressNow(Date.now())
        }

        if (job.status === "completed") {
          setRefreshKey((current) => current + 1)
        }
      } catch (error) {
        setTlpRefreshJob({
          job_id: "local-error",
          server,
          status: "failed",
          phase: "failed",
          completed: 0,
          total: null,
          current_item_id: null,
          target_item_ids: [],
          target_count: 0,
          limit: 0,
          max_age_hours: refreshMaxAgeHours,
          history_days: 3,
          concurrency: 5,
          stats: null,
          error: error instanceof Error ? error.message : "Unknown TLP Auctions error",
          created_at: new Date().toISOString(),
          started_at: null,
          finished_at: new Date().toISOString(),
        })
      }
    }

    void runTlpRefresh()
  }, [server, tlpMaxAgeHours, tlpRefreshJob])

  useEffect(() => {
    if (!tlpAutoRefreshEnabled) {
      return undefined
    }

    const timer = window.setInterval(() => {
      refreshTlpMarketPrices({ refreshKronoWhenEmpty: false })
    }, TLP_AUTO_REFRESH_INTERVAL_MS)

    return () => {
      window.clearInterval(timer)
    }
  }, [refreshTlpMarketPrices, tlpAutoRefreshEnabled])

  const changeTlpMaxAgeHours = useCallback((nextMaxAgeHours: number) => {
    const savedMaxAgeHours = saveTlpMaxAgeHours(nextMaxAgeHours)
    setTlpMaxAgeHours(savedMaxAgeHours)
    return savedMaxAgeHours
  }, [])

  const changeTlpAutoRefreshEnabled = useCallback((enabled: boolean) => {
    const savedEnabled = saveTlpAutoRefreshEnabled(enabled)
    setTlpAutoRefreshEnabled(savedEnabled)
    return savedEnabled
  }, [])

  const changeDealFilters = useCallback((nextFilters: DealFilters) => {
    setPageState({ status: "loading" })
    setDealFilters(nextFilters)
  }, [])

  const changeMarketListingFilters = useCallback((nextFilters: MarketListingFilters) => {
    setPageState({ status: "loading" })
    setMarketListingFilters(nextFilters)
  }, [])

  return (
    <AppLayout
      activePage={activePage}
      pageTitle={pageDefinition.title}
      server={server}
      isRefreshing={pageState.status === "loading"}
      isTlpRefreshing={isTlpRefreshing}
      tlpMaxAgeHours={tlpMaxAgeHours}
      tlpAutoRefreshEnabled={tlpAutoRefreshEnabled}
      onNavigate={navigateTo}
      onServerChange={changeServer}
      onTlpMaxAgeHoursChange={changeTlpMaxAgeHours}
      onTlpAutoRefreshEnabledChange={changeTlpAutoRefreshEnabled}
      onRefresh={refresh}
      onTlpRefresh={refreshTlpMarketPrices}
    >
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{pageDefinition.description}</p>
          </div>
          <StatusLine pageState={pageState} />
        </div>

        <TlpRefreshProgress job={tlpRefreshJob} nowMs={progressNow} />

        {pageState.status === "loading" ? (
          <LoadingState title={pageDefinition.title} />
        ) : pageState.status === "error" ? (
          <ErrorState title={pageDefinition.title} message={pageState.message} onRetry={refresh} />
        ) : (
          <PageContent
            data={pageState.data}
            server={server}
            mageloStatus={mageloStatus}
            dealFilters={dealFilters}
            onDealFiltersChange={changeDealFilters}
            marketListingFilters={marketListingFilters}
            onMarketListingFiltersChange={changeMarketListingFilters}
          />
        )}
      </section>
    </AppLayout>
  )
}

async function fetchPageData(
  route: AppRoute,
  server: string,
  dealFilters: DealFilters,
  marketListingFilters: MarketListingFilters
): Promise<PageData> {
  if (route.kind === "item-detail") {
    return {
      page: "item-detail",
      payload: await fetchItemDetailPageData(route.itemId, server),
    }
  }

  const page = route.pageId

  switch (page) {
    case "dashboard":
      return { page, payload: await fetchDashboardSummary(server) }
    case "deals":
      return { page, payload: await fetchDeals(server, dealFilters) }
    case "market":
      return { page, payload: await fetchMarketListings(server, marketListingFilters) }
    case "items":
      return { page, payload: await fetchItemSearchPreview(server) }
    case "settings":
      return { page, payload: await fetchSettingsStatus(server) }
  }
}

function getInitialRoute(): AppRoute {
  if (typeof window === "undefined") {
    return { kind: "page", pageId: "dashboard" }
  }

  return routeFromPath(window.location.pathname)
}

function pageDefinitionForRoute(route: AppRoute): AppPageDefinition {
  if (route.kind === "item-detail") {
    return {
      id: "items",
      label: "Items",
      path: "/items",
      title: "Item Detail",
      description: "Stats, market price, local history, and source links.",
    }
  }

  return APP_PAGES.find((page) => page.id === route.pageId) ?? APP_PAGES[0]
}

function StatusLine({ pageState }: { pageState: PageState }) {
  if (pageState.status === "loading") {
    return <Badge variant="secondary">Refreshing</Badge>
  }

  if (pageState.status === "error") {
    return <Badge variant="destructive">Error</Badge>
  }

  return (
    <Badge variant="outline" className="rounded-md">
      Updated {formatTime(pageState.loadedAt)}
    </Badge>
  )
}

function TlpRefreshProgress({
  job,
  nowMs,
}: {
  job: TlpPriceRefreshJobStatus | null
  nowMs: number
}) {
  if (job === null) {
    return null
  }

  const running = isRunningTlpJob(job)
  const total = job.total ?? job.target_count
  const hasTotal = total > 0
  const percent = hasTotal ? Math.min(100, Math.round((job.completed * 100) / total)) : job.status === "completed" ? 100 : 0
  const elapsed = formatElapsed(job.started_at ?? job.created_at, nowMs)
  const refreshAge = formatRefreshAge(job.max_age_hours)
  const label = job.status === "failed" ? job.error ?? "TLP Auctions refresh failed" : formatTlpPhase(job.phase)

  return (
    <div className="rounded-lg border bg-card p-3 text-sm shadow-sm" role="status" aria-live="polite">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="font-medium">TLP Auctions price refresh</p>
          <p className="text-muted-foreground">
            {label} · {hasTotal ? `${job.completed}/${total} items` : `${job.completed} items`} · {refreshAge} · {job.concurrency} parallel · {elapsed}
          </p>
        </div>
        <Badge variant={job.status === "failed" ? "destructive" : running ? "secondary" : "outline"}>
          {job.status === "failed" ? "Failed" : running ? `${percent}%` : "Done"}
        </Badge>
      </div>
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}

function isRunningTlpJob(job: TlpPriceRefreshJobStatus | null): boolean {
  return job?.status === "queued" || job?.status === "running"
}

function formatTlpPhase(phase: string): string {
  switch (phase) {
    case "queued":
      return "Waiting to start"
    case "selecting":
      return "Selecting stale items"
    case "selected":
      return "Items selected"
    case "krono":
      return "Refreshing Krono price"
    case "catalog":
      return "Loading TLP catalog"
    case "history":
      return "Refreshing item histories"
    case "catalog_prices":
      return "Refreshing catalog prices"
    case "completed":
      return "Refresh complete"
    case "failed":
      return "Refresh failed"
    default:
      return phase
  }
}

function formatRefreshAge(maxAgeHours: number): string {
  if (maxAgeHours <= 0) {
    return "refresh all"
  }

  return `stale > ${formatTlpMaxAgeHours(maxAgeHours)}h`
}

function formatElapsed(startedAt: string | null, nowMs: number): string {
  if (!startedAt) {
    return "0s"
  }

  const elapsedMs = nowMs - Date.parse(startedAt)
  if (!Number.isFinite(elapsedMs) || elapsedMs <= 0) {
    return "0s"
  }

  const elapsedSeconds = Math.floor(elapsedMs / 1000)
  const minutes = Math.floor(elapsedSeconds / 60)
  const seconds = elapsedSeconds % 60
  return minutes > 0 ? `${minutes}m ${seconds.toString().padStart(2, "0")}s` : `${seconds}s`
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, milliseconds)
  })
}

function PageContent({
  data,
  server,
  mageloStatus,
  dealFilters,
  onDealFiltersChange,
  marketListingFilters,
  onMarketListingFiltersChange,
}: {
  data: PageData
  server: string
  mageloStatus: MageloStatus
  dealFilters: DealFilters
  onDealFiltersChange: (filters: DealFilters) => void
  marketListingFilters: MarketListingFilters
  onMarketListingFiltersChange: (filters: MarketListingFilters) => void
}) {
  switch (data.page) {
    case "dashboard":
      return <DashboardPage summary={data.payload} />
    case "deals":
      return (
        <DealsPage
          deals={data.payload}
          server={server}
          filters={dealFilters}
          onFiltersChange={onDealFiltersChange}
        />
      )
    case "market":
      return (
        <MarketListingsPage
          listings={data.payload}
          server={server}
          filters={marketListingFilters}
          onFiltersChange={onMarketListingFiltersChange}
        />
      )
    case "items":
      return <ItemsPage items={data.payload} server={server} />
    case "item-detail":
      return <ItemDetailPage data={data.payload} server={server} />
    case "settings":
      return <SettingsPage settings={data.payload} mageloStatus={mageloStatus} />
  }
}

function ItemsPage({ items, server }: { items: ItemSearchResult[]; server: string }) {
  return (
    <PagePanel title="Item Index" eyebrow={`${items.length} matches`}>
      {items.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Slot</TableHead>
              <TableHead>Classes</TableHead>
              <TableHead>Flags</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => (
              <TableRow key={item.item_id}>
                <TableCell className="font-medium">
                  <ItemLink
                    itemId={item.item_id}
                    name={item.name}
                    server={server}
                    details={[
                      { label: "Slot", value: item.slot },
                      { label: "Classes", value: item.classes },
                      { label: "Flags", value: item.flags },
                    ]}
                  />
                </TableCell>
                <TableCell>{item.slot ?? "Any"}</TableCell>
                <TableCell>{item.classes ?? "All"}</TableCell>
                <TableCell>{item.flags ?? "None"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <EmptyState label="No items returned" />
      )}
    </PagePanel>
  )
}

function PagePanel({
  title,
  eyebrow,
  children,
}: {
  title: string
  eyebrow: string
  children: ReactNode
}) {
  return (
    <section className="flex flex-col gap-4">
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <h2 className="text-base font-semibold">{title}</h2>
        <Badge variant="outline" className="rounded-md">
          {eyebrow}
        </Badge>
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  )
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{label}</p>
}

export default App
