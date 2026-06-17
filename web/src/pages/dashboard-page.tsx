import {
  BadgePercent,
  Clock3,
  Coins,
  ListChecks,
  TrendingUp,
} from "lucide-react"
import type { ReactNode } from "react"

import { ItemLink } from "@/components/item-link"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { DashboardDealPreview, DashboardSummary } from "@/lib/api"
import { formatDateTime, formatNumber, formatPercent, formatPrice } from "@/lib/format"
import { cn } from "@/lib/utils"

export function DashboardPage({ summary }: { summary: DashboardSummary }) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Server Overview</h2>
          <p className="text-sm text-muted-foreground">
            Recent market activity from the last {summary.recent_window_hours} hours.
          </p>
        </div>
        <Badge variant="outline" className="rounded-md">
          {summary.server}
        </Badge>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Recent listings"
          value={formatNumber(summary.listings_recent_count)}
          description={`Listings seen in the active ${summary.recent_window_hours}h window`}
          icon={<ListChecks aria-hidden="true" />}
        />
        <MetricCard
          title="Deals detected"
          value={formatNumber(summary.deals_recent_count)}
          description={`At least ${formatPercent(summary.min_discount)} below market reference`}
          icon={<BadgePercent aria-hidden="true" />}
          tone="emerald"
        />
        <MetricCard
          title="Krono price"
          value={formatPrice(summary.krono_latest.price_pp)}
          description={summary.krono_latest.confidence ?? "No Krono confidence available"}
          icon={<Coins aria-hidden="true" />}
          tone="amber"
        />
        <MetricCard
          title="Last refresh"
          value={formatDateTime(summary.krono_latest.last_refresh_at)}
          description={summary.krono_latest.source ?? "No Krono refresh found"}
          icon={<Clock3 aria-hidden="true" />}
          compact
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(18rem,0.8fr)]">
        <Card className="min-w-0">
          <CardHeader className="border-b">
            <CardTitle>
              <h3>Top Discounts</h3>
            </CardTitle>
            <CardDescription>
              Highest recent discounts returned by the dashboard summary.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {summary.top_discounts.length > 0 ? (
              <TopDiscountsTable deals={summary.top_discounts} server={summary.server} />
            ) : (
              <EmptyState label="No qualifying discounts in the current window." />
            )}
          </CardContent>
        </Card>

        <Card className="min-w-0">
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2">
              <TrendingUp aria-hidden="true" className="size-4" />
              <h3>Trends</h3>
            </CardTitle>
            <CardDescription>Items seen most often in recent listings.</CardDescription>
          </CardHeader>
          <CardContent>
            {summary.top_seen_items.length > 0 ? (
              <TopSeenItems items={summary.top_seen_items} server={summary.server} />
            ) : (
              <EmptyState label="No item activity in the current window." />
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

function MetricCard({
  title,
  value,
  description,
  icon,
  tone = "neutral",
  compact = false,
}: {
  title: string
  value: string
  description: string
  icon: ReactNode
  tone?: "neutral" | "emerald" | "amber"
  compact?: boolean
}) {
  const toneClass = {
    neutral: "bg-muted/20 text-muted-foreground",
    emerald: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    amber: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
  }[tone]

  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className={cn("break-words", compact ? "text-lg" : "text-2xl")}>
          {value}
        </CardTitle>
        <CardAction>
          <span className={cn("flex size-9 items-center justify-center rounded-md", toneClass)}>
            {icon}
          </span>
        </CardAction>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

function TopDiscountsTable({ deals, server }: { deals: DashboardDealPreview[]; server: string }) {
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
            <TableCell className="min-w-[13rem] whitespace-normal">
              <ItemLink
                itemId={deal.item_id}
                name={deal.item_name}
                server={server}
                details={[
                  { label: "Listed", value: formatPrice(deal.listing_price_pp) },
                  { label: "Market", value: formatPrice(deal.market_price_pp) },
                  { label: "Discount", value: formatPercent(deal.discount_pct) },
                  { label: "Seller", value: deal.seller },
                  { label: "Seen", value: formatDateTime(deal.timestamp) },
                ]}
              />
            </TableCell>
            <TableCell>{deal.price_raw ?? formatPrice(deal.listing_price_pp)}</TableCell>
            <TableCell>
              <div className="grid gap-1">
                <span>{formatPrice(deal.market_price_pp)}</span>
                <span className="text-xs text-muted-foreground">
                  {deal.market_price_source ?? "reference"}
                </span>
              </div>
            </TableCell>
            <TableCell>
              <Badge variant="secondary">{formatPercent(deal.discount_pct)}</Badge>
            </TableCell>
            <TableCell>{deal.seller ?? "Unknown"}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function TopSeenItems({
  items,
  server,
}: {
  items: DashboardSummary["top_seen_items"]
  server: string
}) {
  return (
    <ol className="grid gap-2">
      {items.map((item, index) => (
        <li key={`${item.item_id ?? item.item_name}-${item.last_seen_at}`}>
          <div className="grid gap-2 rounded-md border bg-background px-3 py-2">
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">#{index + 1}</p>
                <ItemLink
                  itemId={item.item_id}
                  name={item.item_name}
                  server={server}
                  details={[
                    { label: "Seen", value: `${formatNumber(item.seen_count)} listings` },
                    { label: "Last seen", value: formatDateTime(item.last_seen_at) },
                  ]}
                />
              </div>
              <Badge variant="outline" className="rounded-md">
                {formatNumber(item.seen_count)}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Last seen {formatDateTime(item.last_seen_at)}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{label}</p>
}
