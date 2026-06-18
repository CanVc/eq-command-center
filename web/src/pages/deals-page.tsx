import { useEffect, useState } from "react"
import type { FormEvent } from "react"
import { Ban, Check, Copy, SlidersHorizontal } from "lucide-react"

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
  onDiscardListing: (listingId: number, reasonCode?: string) => Promise<void>
  onRestoreListing: (listingId: number) => Promise<void>
}

const numberInputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function DealsPage({
  deals,
  server,
  filters,
  onFiltersChange,
  onDiscardListing,
  onRestoreListing,
}: DealsPageProps) {
  const [copiedListingId, setCopiedListingId] = useState<number | null>(null)
  const [reviewingListingId, setReviewingListingId] = useState<number | null>(null)

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

  const discardDeal = async (deal: DealPreview) => {
    setReviewingListingId(deal.listing_id)
    try {
      await onDiscardListing(deal.listing_id, "wrong_unit")
    } finally {
      setReviewingListingId(null)
    }
  }

  const trustDeal = async (deal: DealPreview) => {
    setReviewingListingId(deal.listing_id)
    try {
      await onRestoreListing(deal.listing_id)
    } finally {
      setReviewingListingId(null)
    }
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
          reviewingListingId={reviewingListingId}
          onCopyTell={copyTell}
          onDiscardDeal={discardDeal}
          onTrustDeal={trustDeal}
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
      className="grid gap-3 rounded-lg border bg-card p-3 md:grid-cols-[repeat(5,minmax(0,1fr))_auto]"
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

      <label className="flex h-full min-h-14 items-center gap-2 rounded-lg border bg-background px-3 text-sm">
        <input
          aria-label="Show suspect listings"
          className="size-4 accent-foreground"
          type="checkbox"
          checked={draftFilters.includeSuspect}
          onChange={(event) => updateDraftFilter("includeSuspect", event.target.checked)}
        />
        <span>Show suspect</span>
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
  reviewingListingId,
  onCopyTell,
  onDiscardDeal,
  onTrustDeal,
}: {
  deals: DealPreview[]
  server: string
  copiedListingId: number | null
  reviewingListingId: number | null
  onCopyTell: (deal: DealPreview) => void
  onDiscardDeal: (deal: DealPreview) => void
  onTrustDeal: (deal: DealPreview) => void
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
                <div className="grid gap-1">
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
                  {deal.review_status === "suspect" ? (
                    <Badge variant="outline" className="w-fit rounded-md border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300">
                      Suspect · {formatReviewReason(deal.review_reason_code)}
                    </Badge>
                  ) : null}
                </div>
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
                <div className="flex flex-wrap gap-2">
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
                  {deal.review_status === "suspect" ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      aria-label={`Trust ${deal.item_name}`}
                      disabled={reviewingListingId === deal.listing_id}
                      onClick={() => void onTrustDeal(deal)}
                    >
                      <Check aria-hidden="true" />
                      Keep
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label={`Discard ${deal.item_name}`}
                    disabled={reviewingListingId === deal.listing_id}
                    onClick={() => void onDiscardDeal(deal)}
                  >
                    <Ban aria-hidden="true" />
                    {reviewingListingId === deal.listing_id ? "Saving" : "Discard"}
                  </Button>
                </div>
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

function formatReviewReason(reasonCode: string | null): string {
  switch (reasonCode) {
    case "likely_krono_price_missing_unit":
      return "missing kr"
    case "bare_price_extreme_discount":
      return "bare price"
    case "wrong_unit":
      return "wrong unit"
    case "manual":
      return "manual"
    default:
      return reasonCode ?? "review"
  }
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
