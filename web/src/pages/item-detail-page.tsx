import {
  Activity,
  Coins,
  ExternalLink,
  LineChart,
  ScrollText,
  Shield,
  Sparkles,
} from "lucide-react"
import type { ReactNode } from "react"
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
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
import type {
  ItemCombat,
  ItemDetail,
  ItemDetailPageData,
  ItemListing,
  ItemMarketPrice,
  ItemStats,
  KronoLatest,
} from "@/lib/api"
import { formatDateTime, formatNumber, formatPrice } from "@/lib/format"
import {
  buildExternalItemLinks,
  buildPriceHistory,
  formatKronoEquivalent,
  latestPricedListing,
  type PriceHistoryPoint,
} from "@/lib/item-detail"
import { cn } from "@/lib/utils"

export function ItemDetailPage({ data, server }: { data: ItemDetailPageData; server: string }) {
  const history = buildPriceHistory(data.listings)
  const latestListing = latestPricedListing(data.listings)

  return (
    <section className="flex flex-col gap-4">
      <ItemSummary item={data.item} server={server} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Market median"
          value={formatPrice(data.price.median_pp)}
          description={data.price.market_price_source ?? "No market reference"}
          icon={<Coins aria-hidden="true" />}
        />
        <MetricCard
          title="Local last seen"
          value={formatPrice(latestListing?.price_pp)}
          description={latestListing ? formatDateTime(latestListing.timestamp) : "No priced listing"}
          icon={<Activity aria-hidden="true" />}
          tone="emerald"
        />
        <MetricCard
          title="Krono equivalent"
          value={formatKronoEquivalent(data.price.market_price_pp, data.kronoLatest.price_pp)}
          description={formatKronoDescription(data.kronoLatest)}
          icon={<Sparkles aria-hidden="true" />}
          tone="amber"
        />
        <MetricCard
          title="Samples"
          value={data.price.sample_size === null ? "n/a" : formatNumber(data.price.sample_size)}
          description={data.price.confidence ?? "No price confidence"}
          icon={<LineChart aria-hidden="true" />}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.75fr)]">
        <PriceChartCard history={history} />
        <MarketPriceCard price={data.price} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.75fr)]">
        <StatsCard item={data.item} />
        <SourcesCard item={data.item} server={server} />
      </div>

      {data.item.effects.length > 0 ? <EffectsCard item={data.item} /> : null}

      <ListingsCard listings={data.listings} />
    </section>
  )
}

function ItemSummary({ item, server }: { item: ItemDetail; server: string }) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>
          <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h2 className="break-words text-xl font-semibold">{item.name}</h2>
              <p className="text-sm font-normal text-muted-foreground">
                Item ID {item.item_id} on {server}
              </p>
            </div>
          </div>
        </CardTitle>
        <CardDescription>Local item record, market reference, and recent auction history.</CardDescription>
        <CardAction>
          <Badge variant="outline" className="rounded-md">
            {item.item_type ?? "item"}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        <DescriptionGrid
          rows={[
            { label: "Slot", value: item.slot ?? "Any" },
            { label: "Classes", value: item.classes ?? "All" },
            { label: "Races", value: item.races ?? "All" },
            { label: "Flags", value: item.flags ?? "None" },
            { label: "Source", value: item.source_primary ?? "n/a" },
            { label: "Imported", value: formatDateTime(item.last_imported_at) },
          ]}
        />
      </CardContent>
    </Card>
  )
}

function MetricCard({
  title,
  value,
  description,
  icon,
  tone = "neutral",
}: {
  title: string
  value: string
  description: string
  icon: ReactNode
  tone?: "neutral" | "emerald" | "amber"
}) {
  const toneClass = {
    neutral: "bg-muted/20 text-muted-foreground",
    emerald: "bg-emerald-500/10 text-emerald-700",
    amber: "bg-amber-500/10 text-amber-700",
  }[tone]

  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="break-words text-2xl">{value}</CardTitle>
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

function PriceChartCard({ history }: { history: PriceHistoryPoint[] }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <LineChart aria-hidden="true" className="size-4" />
          <h3>Local Price History</h3>
        </CardTitle>
        <CardDescription>{history.length} priced local listings from market_listings.</CardDescription>
      </CardHeader>
      <CardContent>
        {history.length > 0 ? (
          <div className="h-72 w-full min-w-0" aria-label="Local price history chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="priceHistoryFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--color-chart-2)" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="var(--color-chart-2)" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="timestamp"
                  minTickGap={18}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={formatChartTick}
                />
                <YAxis
                  width={74}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => compactPrice(Number(value))}
                />
                <Tooltip
                  formatter={(value) => [formatPrice(Number(value)), "Price"]}
                  labelFormatter={(value) => formatDateTime(String(value))}
                />
                <Area
                  type="monotone"
                  dataKey="price_pp"
                  stroke="var(--color-chart-2)"
                  fill="url(#priceHistoryFill)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState label="No local priced listings available for this item." />
        )}
      </CardContent>
    </Card>
  )
}

function MarketPriceCard({ price }: { price: ItemMarketPrice }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle>
          <h3>Market Price</h3>
        </CardTitle>
        <CardDescription>{price.source ?? "No external market price imported."}</CardDescription>
      </CardHeader>
      <CardContent>
        <DescriptionGrid
          rows={[
            { label: "Reference", value: formatPrice(price.market_price_pp) },
            { label: "Median", value: formatPrice(price.median_pp) },
            { label: "P25", value: formatPrice(price.p25_pp) },
            { label: "P75", value: formatPrice(price.p75_pp) },
            { label: "Average", value: formatPrice(price.avg_pp) },
            { label: "Min", value: formatPrice(price.min_pp) },
            { label: "Max", value: formatPrice(price.max_pp) },
            {
              label: "Sample size",
              value: price.sample_size === null ? "n/a" : formatNumber(price.sample_size),
            },
            { label: "Confidence", value: price.confidence ?? "n/a" },
            { label: "Refresh", value: formatDateTime(price.last_refresh_at) },
          ]}
        />
      </CardContent>
    </Card>
  )
}

function StatsCard({ item }: { item: ItemDetail }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Shield aria-hidden="true" className="size-4" />
          <h3>Stats</h3>
        </CardTitle>
        <CardDescription>Core stats, primary attributes, resists, and combat values.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <StatGroup
          title="Core"
          stats={[
            ["AC", item.stats.ac],
            ["HP", item.stats.hp],
            ["Mana", item.stats.mana],
            ["Endurance", item.stats.endurance],
          ]}
        />
        <StatGroup
          title="Primary"
          stats={[
            ["STR", item.stats.str],
            ["STA", item.stats.sta],
            ["AGI", item.stats.agi],
            ["DEX", item.stats.dex],
            ["WIS", item.stats.wis],
            ["INT", item.stats.int],
            ["CHA", item.stats.cha],
          ]}
        />
        <StatGroup
          title="Resists"
          stats={[
            ["Magic", item.stats.sv_magic],
            ["Fire", item.stats.sv_fire],
            ["Cold", item.stats.sv_cold],
            ["Poison", item.stats.sv_poison],
            ["Disease", item.stats.sv_disease],
          ]}
        />
        <CombatStats combat={item.combat} levels={item.levels} stats={item.stats} />
      </CardContent>
    </Card>
  )
}

function CombatStats({
  combat,
  levels,
  stats,
}: {
  combat: ItemCombat
  levels: ItemDetail["levels"]
  stats: ItemStats
}) {
  const regenRows = [
    ["HP Regen", stats.hp_regen],
    ["Mana Regen", stats.mana_regen],
    ["End Regen", stats.endurance_regen],
  ] satisfies Array<[string, number | null]>

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <StatGroup
        title="Combat"
        stats={[
          ["Damage", combat.damage],
          ["Delay", combat.delay],
          ["Ratio", combat.ratio === null ? null : combat.ratio.toFixed(2)],
          ["Haste", combat.haste === null ? null : `${formatNumber(combat.haste)}%`],
        ]}
      />
      <StatGroup
        title="Levels and regen"
        stats={[
          ["Required", levels.required_level],
          ["Recommended", levels.recommended_level],
          ...regenRows,
        ]}
      />
    </div>
  )
}

function SourcesCard({ item, server }: { item: ItemDetail; server: string }) {
  const links = buildExternalItemLinks(item, server)

  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <ExternalLink aria-hidden="true" className="size-4" />
          <h3>Sources</h3>
        </CardTitle>
        <CardDescription>External references constructed from the local item record.</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-2">
        {links.map((link) => (
          <Button key={link.label} variant="outline" asChild className="justify-between">
            <a href={link.href} target="_blank" rel="noreferrer">
              {link.label}
              <ExternalLink aria-hidden="true" />
            </a>
          </Button>
        ))}
      </CardContent>
    </Card>
  )
}

function EffectsCard({ item }: { item: ItemDetail }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Sparkles aria-hidden="true" className="size-4" />
          <h3>Effects</h3>
        </CardTitle>
        <CardDescription>{item.effects.length} local item effects.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2">
          {item.effects.map((effect) => (
            <div
              key={effect.effect_slot}
              className="grid gap-1 rounded-md border bg-background px-3 py-2"
            >
              <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
                <p className="break-words text-sm font-medium">
                  {effect.description ?? effect.spell.name ?? `Effect ${effect.effect_slot}`}
                </p>
                <Badge variant="outline" className="w-fit rounded-md">
                  {effect.trigger_type ?? "unknown"}
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">
                {effect.spell.name ?? "No linked spell"} - slot {effect.effect_slot}
              </p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function ListingsCard({ listings }: { listings: ItemListing[] }) {
  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <ScrollText aria-hidden="true" className="size-4" />
          <h3>Local Listings</h3>
        </CardTitle>
        <CardDescription>{listings.length} listings returned by the local history endpoint.</CardDescription>
      </CardHeader>
      <CardContent>
        {listings.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Timestamp</TableHead>
                  <TableHead>Seller</TableHead>
                  <TableHead>Listed name</TableHead>
                  <TableHead>Price raw</TableHead>
                  <TableHead>Price PP</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Confidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {listings.map((listing) => (
                  <TableRow key={listing.listing_id}>
                    <TableCell className="min-w-[10rem]">
                      <time dateTime={listing.timestamp}>{formatDateTime(listing.timestamp)}</time>
                    </TableCell>
                    <TableCell>{listing.seller ?? "Unknown"}</TableCell>
                    <TableCell className="min-w-[13rem] whitespace-normal">
                      {listing.listed_item_name}
                    </TableCell>
                    <TableCell>{listing.price_raw ?? "n/a"}</TableCell>
                    <TableCell>{formatPrice(listing.price_pp)}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="rounded-md">
                        {listing.source}
                      </Badge>
                    </TableCell>
                    <TableCell>{listing.confidence ?? "n/a"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <EmptyState label="No local listings returned for this item." />
        )}
      </CardContent>
    </Card>
  )
}

function DescriptionGrid({ rows }: { rows: Array<{ label: string; value: string }> }) {
  return (
    <dl className="grid gap-2 sm:grid-cols-2">
      {rows.map((row) => (
        <div key={row.label} className="grid gap-1 rounded-md border bg-background px-3 py-2">
          <dt className="text-xs font-medium text-muted-foreground">{row.label}</dt>
          <dd className="min-w-0 break-words text-sm font-medium">{row.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function StatGroup({
  title,
  stats,
}: {
  title: string
  stats: Array<[string, number | string | null]>
}) {
  const visibleStats = stats.filter(([, value]) => value !== null)

  return (
    <div className="grid gap-2">
      <h4 className="text-sm font-medium">{title}</h4>
      {visibleStats.length > 0 ? (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {visibleStats.map(([label, value]) => (
            <div key={label} className="rounded-md border bg-background px-3 py-2">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="break-words text-sm font-semibold">{formatStatValue(value)}</p>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState label={`No ${title.toLowerCase()} stats available.`} />
      )}
    </div>
  )
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{label}</p>
}

function formatKronoDescription(kronoLatest: KronoLatest): string {
  if (kronoLatest.price_pp === null) {
    return "No Krono price available"
  }

  return `${formatPrice(kronoLatest.price_pp)} per Krono`
}

function formatStatValue(value: number | string | null): string {
  if (value === null) {
    return "n/a"
  }

  return typeof value === "number" ? formatNumber(value) : value
}

function formatChartTick(value: string): string {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date)
}

function compactPrice(value: number): string {
  if (!Number.isFinite(value)) {
    return "n/a"
  }

  if (Math.abs(value) >= 1000) {
    return `${Math.round(value / 1000)}k`
  }

  return String(value)
}
