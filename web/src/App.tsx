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
  fetchItemSearchPreview,
  fetchMarketListings,
  fetchSettingsHealth,
  type DashboardSummary,
  type DealFilters,
  type DealPreview,
  type HealthResponse,
  type ItemSearchResult,
  type ListingPreview,
  type MarketListingFilters,
} from "@/lib/api"
import {
  ensureMageloScript,
  getMageloStatus,
  scanMageloItems,
  subscribeMageloStatus,
  type MageloStatus,
} from "@/lib/magelo"
import { APP_PAGES, pageIdFromPath, pathForPage, type AppPageId } from "@/lib/navigation"
import { readPreferredServer, savePreferredServer } from "@/lib/server-preference"
import { DashboardPage } from "@/pages/dashboard-page"
import { DealsPage } from "@/pages/deals-page"
import { MarketListingsPage } from "@/pages/market-listings-page"

type PageData =
  | { page: "dashboard"; payload: DashboardSummary }
  | { page: "deals"; payload: DealPreview[] }
  | { page: "market"; payload: ListingPreview[] }
  | { page: "items"; payload: ItemSearchResult[] }
  | { page: "settings"; payload: HealthResponse }

type PageState =
  | { status: "loading" }
  | { status: "ready"; data: PageData; loadedAt: Date }
  | { status: "error"; message: string }

function App() {
  const [activePage, setActivePage] = useState<AppPageId>(() => getInitialPage())
  const [server, setServer] = useState(() => readPreferredServer())
  const [dealFilters, setDealFilters] = useState<DealFilters>(DEFAULT_DEAL_FILTERS)
  const [marketListingFilters, setMarketListingFilters] = useState<MarketListingFilters>(
    DEFAULT_MARKET_LISTING_FILTERS
  )
  const [refreshKey, setRefreshKey] = useState(0)
  const [mageloStatus, setMageloStatus] = useState<MageloStatus>(() => getMageloStatus())
  const [pageState, setPageState] = useState<PageState>({ status: "loading" })

  const pageDefinition = APP_PAGES.find((page) => page.id === activePage) ?? APP_PAGES[0]

  useEffect(() => {
    const handlePopState = () => {
      setPageState({ status: "loading" })
      setActivePage(pageIdFromPath(window.location.pathname))
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
        const data = await fetchPageData(activePage, server, dealFilters, marketListingFilters)
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
  }, [activePage, dealFilters, marketListingFilters, refreshKey, server])

  const navigateTo = useCallback((pageId: AppPageId) => {
    const nextPath = pathForPage(pageId)

    if (pageId === activePage && window.location.pathname === nextPath) {
      return
    }

    if (window.location.pathname !== nextPath) {
      window.history.pushState(null, "", nextPath)
    }

    setPageState({ status: "loading" })
    setActivePage(pageId)
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
    setRefreshKey((current) => current + 1)
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
      server={server}
      isRefreshing={pageState.status === "loading"}
      onNavigate={navigateTo}
      onServerChange={changeServer}
      onRefresh={refresh}
    >
      <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <p className="text-sm text-muted-foreground">{pageDefinition.description}</p>
          </div>
          <StatusLine pageState={pageState} />
        </div>

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
  page: AppPageId,
  server: string,
  dealFilters: DealFilters,
  marketListingFilters: MarketListingFilters
): Promise<PageData> {
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
      return { page, payload: await fetchSettingsHealth(server) }
  }
}

function getInitialPage(): AppPageId {
  if (typeof window === "undefined") {
    return "dashboard"
  }

  return pageIdFromPath(window.location.pathname)
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
      Updated {pageState.loadedAt.toLocaleTimeString()}
    </Badge>
  )
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
    case "settings":
      return <SettingsPage health={data.payload} server={server} mageloStatus={mageloStatus} />
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

function SettingsPage({
  health,
  server,
  mageloStatus,
}: {
  health: HealthResponse
  server: string
  mageloStatus: MageloStatus
}) {
  return (
    <PagePanel title="Local Settings" eyebrow={health.status}>
      <SimpleList
        rows={[
          { label: "Active server", value: server },
          { label: "API health", value: health.status },
          { label: "SQLite", value: health.db_path },
          { label: "Magelo", value: formatMageloStatus(mageloStatus) },
        ]}
      />
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

function SimpleList({ rows }: { rows: Array<{ label: string; value: string }> }) {
  return (
    <dl className="grid gap-2">
      {rows.map((row) => (
        <div
          key={row.label}
          className="grid gap-1 rounded-md border bg-background px-3 py-2 sm:grid-cols-[10rem_1fr]"
        >
          <dt className="text-sm text-muted-foreground">{row.label}</dt>
          <dd className="min-w-0 break-words text-sm font-medium">{row.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{label}</p>
}

function formatMageloStatus(status: MageloStatus): string {
  if (status === "loaded") {
    return "loaded"
  }

  if (status === "loading") {
    return "loading"
  }

  return "not loaded"
}

export default App
