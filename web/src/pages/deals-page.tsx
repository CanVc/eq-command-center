import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Copy, SlidersHorizontal } from "lucide-react"

import { ItemLink } from "@/components/item-link"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { DealFilters, DealPreview } from "@/lib/api"
import {
  buildTellMessage,
  dealFiltersKey,
  dealFiltersToDraft,
  discountBadgeClassName,
  normalizeDealFilters,
  type DraftDealFilters,
} from "@/lib/deals"
import { formatDateTime, formatNumber, formatPercent, formatPrice } from "@/lib/format"
import { cn } from "@/lib/utils"

type DealsPageProps = {
  deals: DealPreview[]
  server: string
  filters: DealFilters
  onFiltersChange: (filters: DealFilters) => void
}

const numberInputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function DealsPage({ deals, server, filters, onFiltersChange }: DealsPageProps) {
  const [copiedListingId, setCopiedListingId] = useState<number | null>(null)

  useEffect(() => {
    if (copiedListingId === null) {
      return undefined
    }

    const timer = window.setTimeout(() => {
      setCopiedListingId(null)
    }, 1500)

    return () => {
      window.clearTimeout(timer)
    }
  }, [copiedListingId])

  const copyTell = async (deal: DealPreview) => {
    await copyText(buildTellMessage(deal))
    setCopiedListingId(deal.listing_id)
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Deal Queue</h2>
          <p className="text-sm text-muted-foreground">{deals.length} listings</p>
        </div>
        <Badge variant="outline" className="rounded-md">
          min {formatPercent(filters.minDiscount)}
        </Badge>
      </div>

      <DealFiltersForm
        key={dealFiltersKey(filters)}
        filters={filters}
        onFiltersChange={onFiltersChange}
      />

      {deals.length > 0 ? (
        <DealsTable
          deals={deals}
          server={server}
          copiedListingId={copiedListingId}
          onCopyTell={copyTell}
        />
      ) : (
        <EmptyState />
      )}
    </section>
  )
}

function DealFiltersForm({
  filters,
  onFiltersChange,
}: {
  filters: DealFilters
  onFiltersChange: (filters: DealFilters) => void
}) {
  const [draftFilters, setDraftFilters] = useState(() => dealFiltersToDraft(filters))

  const updateDraftFilter = (key: keyof DraftDealFilters, value: string | boolean) => {
    setDraftFilters((current) => ({ ...current, [key]: value }))
  }

  const applyFilters = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onFiltersChange(normalizeDealFilters(draftFilters))
  }

  return (
    <form
      aria-label="Deal filters"
      onSubmit={applyFilters}
      className="grid gap-3 rounded-lg border bg-card p-3 md:grid-cols-[repeat(4,minmax(0,1fr))_auto]"
    >
      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Min discount</span>
        <input
          aria-label="Minimum discount"
          className={numberInputClassName}
          type="number"
          min={0}
          max={100}
          step={1}
          value={draftFilters.minDiscount}
          onChange={(event) => updateDraftFilter("minDiscount", event.target.value)}
        />
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Min price</span>
        <input
          aria-label="Minimum price"
          className={numberInputClassName}
          type="number"
          min={0}
          step={1}
          value={draftFilters.minPricePp}
          onChange={(event) => updateDraftFilter("minPricePp", event.target.value)}
        />
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Limit</span>
        <input
          aria-label="Limit"
          className={numberInputClassName}
          type="number"
          min={1}
          max={500}
          step={1}
          value={draftFilters.limit}
          onChange={(event) => updateDraftFilter("limit", event.target.value)}
        />
      </label>

      <label className="flex h-full min-h-14 items-center gap-2 rounded-lg border bg-background px-3 text-sm">
        <input
          aria-label="Resolved only"
          className="size-4 accent-foreground"
          type="checkbox"
          checked={draftFilters.resolvedOnly}
          onChange={(event) => updateDraftFilter("resolvedOnly", event.target.checked)}
        />
        <span>Resolved only</span>
      </label>

      <div className="flex items-end">
        <Button type="submit" className="w-full md:w-auto">
          <SlidersHorizontal aria-hidden="true" />
          Apply
        </Button>
      </div>
    </form>
  )
}

function DealsTable({
  deals,
  server,
  copiedListingId,
  onCopyTell,
}: {
  deals: DealPreview[]
  server: string
  copiedListingId: number | null
  onCopyTell: (deal: DealPreview) => void
}) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Item</TableHead>
            <TableHead>Seen price</TableHead>
            <TableHead>Market price</TableHead>
            <TableHead>Discount</TableHead>
            <TableHead>Seller</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {deals.map((deal) => (
            <TableRow key={deal.listing_id}>
              <TableCell className="min-w-[14rem] whitespace-normal">
                <ItemLink
                  itemId={deal.item_id}
                  name={deal.item_name}
                  server={server}
                  details={[
                    { label: "Seen", value: deal.price_raw ?? formatPrice(deal.listing_price_pp) },
                    { label: "Market", value: formatPrice(deal.market_price_pp) },
                    { label: "Discount", value: formatPercent(deal.discount_pct) },
                    { label: "Seller", value: deal.seller },
                    { label: "Date", value: formatDateTime(deal.timestamp) },
                  ]}
                />
              </TableCell>
              <TableCell>{deal.price_raw ?? formatPrice(deal.listing_price_pp)}</TableCell>
              <TableCell>
                <div className="grid min-w-[7rem] gap-1">
                  <span>{formatPrice(deal.market_price_pp)}</span>
                  <span className="text-xs text-muted-foreground">
                    +{formatPrice(deal.potential_profit_pp)}
                  </span>
                </div>
              </TableCell>
              <TableCell>
                <DiscountBadge value={deal.discount_pct} />
              </TableCell>
              <TableCell>{deal.seller ?? "Unknown"}</TableCell>
              <TableCell>{formatDateTime(deal.timestamp)}</TableCell>
              <TableCell>{formatScore(deal.score)}</TableCell>
              <TableCell>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label={`Copy tell for ${deal.item_name}`}
                  onClick={() => void onCopyTell(deal)}
                >
                  <Copy aria-hidden="true" />
                  {copiedListingId === deal.listing_id ? "Copied" : "Tell"}
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function DiscountBadge({ value }: { value: number }) {
  return (
    <Badge variant="outline" className={cn("rounded-md", discountBadgeClassName(value))}>
      {formatPercent(value)}
    </Badge>
  )
}

function EmptyState() {
  return (
    <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
      No deals match the active filters.
    </p>
  )
}

function formatScore(value: number): string {
  return Number.isInteger(value) ? formatNumber(value) : value.toFixed(1)
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement("textarea")
  textarea.value = text
  textarea.style.position = "fixed"
  textarea.style.opacity = "0"
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand("copy")
  textarea.remove()
}
