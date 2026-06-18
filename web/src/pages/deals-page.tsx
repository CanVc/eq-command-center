import { Fragment, useEffect, useState } from "react"
import type { FormEvent, ReactNode } from "react"
import { Ban, Check, Copy, ScrollText, SlidersHorizontal } from "lucide-react"

import { ItemLink } from "@/components/item-link"
import { RawSalePanel } from "@/components/raw-sale-panel"
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
import type { DealFilters, DealPreview, DealSortBy, DealSortDirection } from "@/lib/api"
import {
  buildTellMessage,
  dealFiltersKey,
  dealFiltersToDraft,
  discountBadgeClassName,
  normalizeDealFilters,
  todayDateInputValue,
  type DraftDealFilters,
} from "@/lib/deals"
import { copyText } from "@/lib/clipboard"
import { formatDateTime, formatNumber, formatPercent, formatPrice } from "@/lib/format"
import { cn } from "@/lib/utils"

type DealsPageProps = {
  deals: DealPreview[]
  server: string
  filters: DealFilters
  onFiltersChange: (filters: DealFilters) => void
  onDiscardListing: (listingId: number, reasonCode?: string) => Promise<void>
  onRestoreListing: (listingId: number) => Promise<void>
  onDiscardSimilarListings: (listingId: number, reasonCode?: string) => Promise<void>
  onRestoreSimilarListings: (listingId: number) => Promise<void>
}

const inputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

const defaultSortDirectionByColumn: Record<DealSortBy, DealSortDirection> = {
  item: "asc",
  seen_price: "desc",
  market_price: "desc",
  discount: "desc",
  seller: "asc",
  date: "desc",
  score: "desc",
}

export function DealsPage({
  deals,
  server,
  filters,
  onFiltersChange,
  onDiscardListing,
  onRestoreListing,
  onDiscardSimilarListings,
  onRestoreSimilarListings,
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

  const discardDeal = async (deal: DealPreview, similar = false) => {
    setReviewingListingId(deal.listing_id)
    try {
      if (similar) {
        await onDiscardSimilarListings(deal.listing_id, "wrong_unit")
      } else {
        await onDiscardListing(deal.listing_id, "wrong_unit")
      }
    } finally {
      setReviewingListingId(null)
    }
  }

  const trustDeal = async (deal: DealPreview, similar = false) => {
    setReviewingListingId(deal.listing_id)
    try {
      if (similar) {
        await onRestoreSimilarListings(deal.listing_id)
      } else {
        await onRestoreListing(deal.listing_id)
      }
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
          filters={filters}
          onFiltersChange={onFiltersChange}
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
    onFiltersChange({
      ...normalizeDealFilters(draftFilters),
      sortBy: filters.sortBy,
      sortDir: filters.sortDir,
    })
  }

  return (
    <form
      aria-label="Deal filters"
      onSubmit={applyFilters}
      className="grid gap-3 rounded-lg border bg-card p-3 md:grid-cols-2 xl:grid-cols-[repeat(6,minmax(0,1fr))_auto]"
    >
      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Item</span>
        <input
          aria-label="Item filter"
          className={inputClassName}
          type="search"
          placeholder="Fungi, crown..."
          value={draftFilters.item}
          onChange={(event) => updateDraftFilter("item", event.target.value)}
        />
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Seller</span>
        <input
          aria-label="Seller filter"
          className={inputClassName}
          type="search"
          placeholder="Seller name"
          value={draftFilters.seller}
          onChange={(event) => updateDraftFilter("seller", event.target.value)}
        />
      </label>

      <label className="grid gap-1.5 text-sm md:col-span-2 xl:col-span-2">
        <span className="text-xs font-medium text-muted-foreground">Since date</span>
        <div className="flex gap-2">
          <input
            aria-label="Deals since date"
            className={inputClassName}
            type="date"
            value={draftFilters.dateFrom}
            onChange={(event) => updateDraftFilter("dateFrom", event.target.value)}
          />
          <Button
            type="button"
            variant="outline"
            size="lg"
            onClick={() => updateDraftFilter("dateFrom", todayDateInputValue())}
          >
            Today
          </Button>
          <Button type="button" variant="outline" size="lg" onClick={() => updateDraftFilter("dateFrom", "")}>
            All
          </Button>
        </div>
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Min discount</span>
        <input
          aria-label="Minimum discount"
          className={inputClassName}
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
          className={inputClassName}
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
          className={inputClassName}
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
  filters,
  onFiltersChange,
  onCopyTell,
  onDiscardDeal,
  onTrustDeal,
}: {
  deals: DealPreview[]
  server: string
  copiedListingId: number | null
  reviewingListingId: number | null
  filters: DealFilters
  onFiltersChange: (filters: DealFilters) => void
  onCopyTell: (deal: DealPreview) => void
  onDiscardDeal: (deal: DealPreview, similar?: boolean) => void
  onTrustDeal: (deal: DealPreview, similar?: boolean) => void
}) {
  const [rawListingId, setRawListingId] = useState<number | null>(null)

  const changeSort = (sortBy: DealSortBy) => {
    const sortDir = filters.sortBy === sortBy
      ? toggleSortDirection(filters.sortDir)
      : defaultSortDirectionByColumn[sortBy]
    onFiltersChange({ ...filters, sortBy, sortDir })
  }

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead filters={filters} sortBy="item" onSortChange={changeSort}>Item</SortableTableHead>
            <SortableTableHead filters={filters} sortBy="seen_price" onSortChange={changeSort}>Seen price</SortableTableHead>
            <SortableTableHead filters={filters} sortBy="market_price" onSortChange={changeSort}>Market price</SortableTableHead>
            <SortableTableHead filters={filters} sortBy="discount" onSortChange={changeSort}>Discount</SortableTableHead>
            <SortableTableHead filters={filters} sortBy="seller" onSortChange={changeSort}>Seller</SortableTableHead>
            <SortableTableHead filters={filters} sortBy="date" onSortChange={changeSort}>Date</SortableTableHead>
            <SortableTableHead filters={filters} sortBy="score" onSortChange={changeSort}>Score</SortableTableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {deals.map((deal) => {
            const isRawOpen = rawListingId === deal.listing_id

            return (
              <Fragment key={deal.listing_id}>
                <TableRow>
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
                        aria-label={`Show raw sale for ${deal.item_name}`}
                        aria-expanded={isRawOpen}
                        onClick={() => setRawListingId(isRawOpen ? null : deal.listing_id)}
                      >
                        <ScrollText aria-hidden="true" />
                        Raw
                      </Button>
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
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        aria-label={`Discard similar ${deal.item_name}`}
                        disabled={reviewingListingId === deal.listing_id || !deal.resolved}
                        onClick={() => void onDiscardDeal(deal, true)}
                      >
                        <Ban aria-hidden="true" />
                        Similar
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
                {isRawOpen ? (
                  <TableRow>
                    <TableCell colSpan={8} className="bg-muted/30 p-3">
                      <RawSalePanel rawLine={deal.raw_line} />
                    </TableCell>
                  </TableRow>
                ) : null}
              </Fragment>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

function SortableTableHead({
  filters,
  sortBy,
  onSortChange,
  children,
}: {
  filters: DealFilters
  sortBy: DealSortBy
  onSortChange: (sortBy: DealSortBy) => void
  children: ReactNode
}) {
  const active = filters.sortBy === sortBy
  const indicator = active ? (filters.sortDir === "asc" ? "↑" : "↓") : "↕"

  return (
    <TableHead aria-sort={active ? sortDirectionToAria(filters.sortDir) : undefined}>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        onClick={() => onSortChange(sortBy)}
      >
        <span>{children}</span>
        <span aria-hidden="true" className={cn("text-xs", active ? "text-foreground" : "text-muted-foreground")}>
          {indicator}
        </span>
      </button>
    </TableHead>
  )
}

function toggleSortDirection(sortDir: DealSortDirection): DealSortDirection {
  return sortDir === "asc" ? "desc" : "asc"
}

function sortDirectionToAria(sortDir: DealSortDirection): "ascending" | "descending" {
  return sortDir === "asc" ? "ascending" : "descending"
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

