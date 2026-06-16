import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"

import { AppLayout } from "@/components/app-layout"
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
  fetchDashboardSummary,
  fetchDealsPreview,
  fetchItemSearchPreview,
  fetchListingsPreview,
  fetchSettingsHealth,
  type DashboardSummary,
  type DealPreview,
  type HealthResponse,
  type ItemSearchResult,
  type ListingPreview,
} from "@/lib/api"
import { APP_PAGES, pageIdFromPath, pathForPage, type AppPageId } from "@/lib/navigation"
import { readPreferredServer, savePreferredServer } from "@/lib/server-preference"

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
  const [refreshKey, setRefreshKey] = useState(0)
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
    let isActive = true

    async function loadPage() {
      try {
        const data = await fetchPageData(activePage, server)
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
  }, [activePage, refreshKey, server])

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
          <PageContent data={pageState.data} server={server} />
        )}
      </section>
    </AppLayout>
  )
}

async function fetchPageData(page: AppPageId, server: string): Promise<PageData> {
  switch (page) {
    case "dashboard":
      return { page, payload: await fetchDashboardSummary(server) }
    case "deals":
      return { page, payload: await fetchDealsPreview(server) }
    case "market":
      return { page, payload: await fetchListingsPreview(server) }
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

function PageContent({ data, server }: { data: PageData; server: string }) {
  switch (data.page) {
    case "dashboard":
      return <DashboardPage summary={data.payload} />
    case "deals":
      return <DealsPage deals={data.payload} />
    case "market":
      return <MarketPage listings={data.payload} />
    case "items":
      return <ItemsPage items={data.payload} />
    case "settings":
      return <SettingsPage health={data.payload} server={server} />
  }
}

function DashboardPage({ summary }: { summary: DashboardSummary }) {
  return (
    <PagePanel title="Server Overview" eyebrow={summary.server}>
      <MetricGrid>
        <Metric label="Recent listings" value={formatNumber(summary.listings_recent_count)} />
        <Metric label="Deals detected" value={formatNumber(summary.deals_recent_count)} tone="emerald" />
        <Metric label="Krono" value={formatPrice(summary.krono_latest.price_pp)} tone="amber" />
      </MetricGrid>

      <div className="grid gap-4 lg:grid-cols-2">
        <DataBlock title="Top Discounts">
          {summary.top_discounts.length > 0 ? (
            <DealsTable deals={summary.top_discounts} />
          ) : (
            <EmptyState label="No discounts returned" />
          )}
        </DataBlock>
        <DataBlock title="Most Seen Items">
          {summary.top_seen_items.length > 0 ? (
            <SimpleList
              rows={summary.top_seen_items.map((item) => ({
                label: item.item_name,
                value: `${item.seen_count} seen`,
              }))}
            />
          ) : (
            <EmptyState label="No item activity returned" />
          )}
        </DataBlock>
      </div>
    </PagePanel>
  )
}

function DealsPage({ deals }: { deals: DealPreview[] }) {
  return (
    <PagePanel title="Deal Queue" eyebrow={`${deals.length} rows`}>
      {deals.length > 0 ? <DealsTable deals={deals} /> : <EmptyState label="No deals returned" />}
    </PagePanel>
  )
}

function MarketPage({ listings }: { listings: ListingPreview[] }) {
  return (
    <PagePanel title="Recent Listings" eyebrow={`${listings.length} rows`}>
      {listings.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Seller</TableHead>
              <TableHead>Price</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {listings.map((listing) => (
              <TableRow key={listing.listing_id}>
                <TableCell className="font-medium">{listing.item_name}</TableCell>
                <TableCell>{listing.seller ?? "Unknown"}</TableCell>
                <TableCell>{listing.price_raw ?? formatPrice(listing.price_pp)}</TableCell>
                <TableCell>
                  <Badge variant={listing.resolved ? "secondary" : "outline"}>
                    {listing.source}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <EmptyState label="No listings returned" />
      )}
    </PagePanel>
  )
}

function ItemsPage({ items }: { items: ItemSearchResult[] }) {
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
                <TableCell className="font-medium">{item.name}</TableCell>
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

function SettingsPage({ health, server }: { health: HealthResponse; server: string }) {
  return (
    <PagePanel title="Local Settings" eyebrow={health.status}>
      <SimpleList
        rows={[
          { label: "Active server", value: server },
          { label: "API health", value: health.status },
          { label: "SQLite", value: health.db_path },
          { label: "Magelo", value: "not loaded" },
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

function MetricGrid({ children }: { children: ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-3">{children}</div>
}

function Metric({
  label,
  value,
  tone = "neutral",
}: {
  label: string
  value: string
  tone?: "neutral" | "emerald" | "amber"
}) {
  const toneClass = {
    neutral: "border-border bg-muted/20",
    emerald: "border-emerald-500/25 bg-emerald-500/10",
    amber: "border-amber-500/30 bg-amber-500/10",
  }[tone]

  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  )
}

function DataBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-md border bg-background">
      <h3 className="border-b px-3 py-2 text-sm font-medium">{title}</h3>
      <div className="p-3">{children}</div>
    </section>
  )
}

function DealsTable({ deals }: { deals: DealPreview[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Item</TableHead>
          <TableHead>Listed</TableHead>
          <TableHead>Market</TableHead>
          <TableHead>Discount</TableHead>
          <TableHead>Seller</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {deals.map((deal) => (
          <TableRow key={deal.listing_id}>
            <TableCell className="font-medium">{deal.item_name}</TableCell>
            <TableCell>{formatPrice(deal.listing_price_pp)}</TableCell>
            <TableCell>{formatPrice(deal.market_price_pp)}</TableCell>
            <TableCell>
              <Badge variant="secondary">{deal.discount_pct.toFixed(1)}%</Badge>
            </TableCell>
            <TableCell>{deal.seller ?? "Unknown"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
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

function formatPrice(value: number | null): string {
  if (value === null) {
    return "n/a"
  }

  return `${formatNumber(value)}pp`
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value)
}

export default App
