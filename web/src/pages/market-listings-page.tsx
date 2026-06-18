import { Ban, ListPlus, RotateCcw, Search, ScrollText, X } from "lucide-react"
import { Fragment, useState } from "react"
import type { FormEvent } from "react"

import { ItemLink } from "@/components/item-link"
import { RawSalePanel } from "@/components/raw-sale-panel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { ListingPreview, ListingReviewStatusFilter, MarketListingFilters } from "@/lib/api"
import { formatDateTime, formatPrice } from "@/lib/format"
import {
  canLoadMoreListings,
  expandMarketListingLimit,
  resetMarketListingSearch,
} from "@/lib/market-listings"
import { cn } from "@/lib/utils"

type MarketListingsPageProps = {
  listings: ListingPreview[]
  server: string
  filters: MarketListingFilters
  onFiltersChange: (filters: MarketListingFilters) => void
  onDiscardListing: (listingId: number, reasonCode?: string) => Promise<void>
  onRestoreListing: (listingId: number) => Promise<void>
  onDiscardSimilarListings: (listingId: number, reasonCode?: string) => Promise<void>
  onRestoreSimilarListings: (listingId: number) => Promise<void>
}

const searchInputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function MarketListingsPage({
  listings,
  server,
  filters,
  onFiltersChange,
  onDiscardListing,
  onRestoreListing,
  onDiscardSimilarListings,
  onRestoreSimilarListings,
}: MarketListingsPageProps) {
  const [draftQuery, setDraftQuery] = useState(filters.query)
  const [reviewingListingId, setReviewingListingId] = useState<number | null>(null)
  const canLoadMore = canLoadMoreListings(listings.length, filters.limit)

  const applySearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onFiltersChange(resetMarketListingSearch(draftQuery, filters.reviewStatus))
  }

  const clearSearch = () => {
    setDraftQuery("")
    onFiltersChange(resetMarketListingSearch("", filters.reviewStatus))
  }

  const changeReviewStatus = (reviewStatus: ListingReviewStatusFilter) => {
    onFiltersChange(resetMarketListingSearch(draftQuery, reviewStatus))
  }

  const discardListing = async (listingId: number, similar = false) => {
    setReviewingListingId(listingId)
    try {
      if (similar) {
        await onDiscardSimilarListings(listingId, "manual")
      } else {
        await onDiscardListing(listingId, "manual")
      }
    } finally {
      setReviewingListingId(null)
    }
  }

  const restoreListing = async (listingId: number, similar = false) => {
    setReviewingListingId(listingId)
    try {
      if (similar) {
        await onRestoreSimilarListings(listingId)
      } else {
        await onRestoreListing(listingId)
      }
    } finally {
      setReviewingListingId(null)
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Raw Listings</h2>
          <p className="text-sm text-muted-foreground">{listings.length} listings loaded</p>
        </div>
        <Badge variant="outline" className="rounded-md">
          limit {filters.limit}
        </Badge>
      </div>

      <form
        aria-label="Listing search"
        onSubmit={applySearch}
        className="grid gap-3 rounded-lg border bg-card p-3 md:grid-cols-[minmax(0,1fr)_12rem_auto]"
      >
        <label className="grid gap-1.5 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Search</span>
          <input
            aria-label="Search listings"
            className={searchInputClassName}
            value={draftQuery}
            placeholder="Item or seller"
            onChange={(event) => setDraftQuery(event.target.value)}
          />
        </label>

        <label className="grid gap-1.5 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Review status</span>
          <select
            aria-label="Review status"
            className={searchInputClassName}
            value={filters.reviewStatus}
            onChange={(event) => changeReviewStatus(event.target.value as ListingReviewStatusFilter)}
          >
            <option value="active">Active</option>
            <option value="suspect">Suspect</option>
            <option value="discarded">Discarded</option>
            <option value="all">All</option>
          </select>
        </label>

        <div className="flex flex-wrap items-end gap-2">
          <Button type="submit" className="w-full sm:w-auto">
            <Search aria-hidden="true" />
            Search
          </Button>
          {filters.query ? (
            <Button type="button" variant="outline" className="w-full sm:w-auto" onClick={clearSearch}>
              <X aria-hidden="true" />
              Clear
            </Button>
          ) : null}
        </div>
      </form>

      {listings.length > 0 ? (
        <ListingsTable
          listings={listings}
          server={server}
          reviewingListingId={reviewingListingId}
          onDiscardListing={discardListing}
          onRestoreListing={restoreListing}
        />
      ) : (
        <EmptyState filtered={!!filters.query || filters.reviewStatus !== "active"} />
      )}

      {canLoadMore ? (
        <div className="flex justify-center">
          <Button
            type="button"
            variant="outline"
            onClick={() => onFiltersChange(expandMarketListingLimit(filters))}
          >
            <ListPlus aria-hidden="true" />
            Load more
          </Button>
        </div>
      ) : null}
    </section>
  )
}

function ListingsTable({
  listings,
  server,
  reviewingListingId,
  onDiscardListing,
  onRestoreListing,
}: {
  listings: ListingPreview[]
  server: string
  reviewingListingId: number | null
  onDiscardListing: (listingId: number, similar?: boolean) => void
  onRestoreListing: (listingId: number, similar?: boolean) => void
}) {
  const [rawListingId, setRawListingId] = useState<number | null>(null)

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Timestamp</TableHead>
            <TableHead>Seller</TableHead>
            <TableHead>Item</TableHead>
            <TableHead>Price raw</TableHead>
            <TableHead>Price PP</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Confidence</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Review</TableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {listings.map((listing) => {
            const isRawOpen = rawListingId === listing.listing_id

            return (
              <Fragment key={listing.listing_id}>
                <TableRow>
                  <TableCell className="min-w-[10rem]">
                    <time dateTime={listing.timestamp}>{formatDateTime(listing.timestamp)}</time>
                  </TableCell>
                  <TableCell>{listing.seller ?? "Unknown"}</TableCell>
                  <TableCell className="min-w-[14rem] whitespace-normal">
                    <ItemLink
                      itemId={listing.item_id}
                      name={listing.item_name}
                      server={server}
                      details={[
                        { label: "Seller", value: listing.seller },
                        { label: "Raw price", value: listing.price_raw },
                        { label: "Price PP", value: formatPrice(listing.price_pp) },
                        { label: "Source", value: listing.source },
                        { label: "Confidence", value: listing.confidence },
                        { label: "Seen", value: formatDateTime(listing.timestamp) },
                      ]}
                    />
                  </TableCell>
                  <TableCell>{listing.price_raw ?? "n/a"}</TableCell>
                  <TableCell>{formatPrice(listing.price_pp)}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="rounded-md">
                      {listing.source}
                    </Badge>
                  </TableCell>
                  <TableCell>{listing.confidence ?? "n/a"}</TableCell>
                  <TableCell>
                    <ResolvedBadge resolved={listing.resolved} />
                  </TableCell>
                  <TableCell>
                    <ReviewBadge status={listing.review_status} reasonCode={listing.review_reason_code} />
                  </TableCell>
                  <TableCell>
                    <ListingActions
                      listing={listing}
                      disabled={reviewingListingId === listing.listing_id}
                      rawOpen={isRawOpen}
                      onToggleRaw={() => setRawListingId(isRawOpen ? null : listing.listing_id)}
                      onDiscardListing={onDiscardListing}
                      onRestoreListing={onRestoreListing}
                    />
                  </TableCell>
                </TableRow>
                {isRawOpen ? (
                  <TableRow>
                    <TableCell colSpan={10} className="bg-muted/30 p-3">
                      <RawSalePanel rawLine={listing.raw_line} />
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

function ListingActions({
  listing,
  disabled,
  rawOpen,
  onToggleRaw,
  onDiscardListing,
  onRestoreListing,
}: {
  listing: ListingPreview
  disabled: boolean
  rawOpen: boolean
  onToggleRaw: () => void
  onDiscardListing: (listingId: number, similar?: boolean) => void
  onRestoreListing: (listingId: number, similar?: boolean) => void
}) {
  if (listing.review_status === "discarded") {
    return (
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label={`Show raw sale for ${listing.item_name}`}
          aria-expanded={rawOpen}
          onClick={onToggleRaw}
        >
          <ScrollText aria-hidden="true" />
          Raw
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => void onRestoreListing(listing.listing_id)}
        >
          <RotateCcw aria-hidden="true" />
          Restore
        </Button>
        {listing.resolved ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={disabled}
            onClick={() => void onRestoreListing(listing.listing_id, true)}
          >
            <RotateCcw aria-hidden="true" />
            Similar
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label={`Show raw sale for ${listing.item_name}`}
        aria-expanded={rawOpen}
        onClick={onToggleRaw}
      >
        <ScrollText aria-hidden="true" />
        Raw
      </Button>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        onClick={() => void onDiscardListing(listing.listing_id)}
      >
        <Ban aria-hidden="true" />
        Discard
      </Button>
      {listing.resolved ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => void onDiscardListing(listing.listing_id, true)}
        >
          <Ban aria-hidden="true" />
          Similar
        </Button>
      ) : null}
      {listing.review_status === "suspect" ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => void onRestoreListing(listing.listing_id)}
        >
          <RotateCcw aria-hidden="true" />
          Keep
        </Button>
      ) : null}
    </div>
  )
}

function ResolvedBadge({ resolved }: { resolved: boolean }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-md",
        resolved
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
      )}
    >
      {resolved ? "Resolved" : "Pending"}
    </Badge>
  )
}

function ReviewBadge({ status, reasonCode }: { status: string; reasonCode: string | null }) {
  if (status === "discarded") {
    return (
      <Badge variant="outline" className="rounded-md border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300">
        Discarded · {formatReviewReason(reasonCode)}
      </Badge>
    )
  }

  if (status === "suspect") {
    return (
      <Badge variant="outline" className="rounded-md border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300">
        Suspect · {formatReviewReason(reasonCode)}
      </Badge>
    )
  }

  return (
    <Badge variant="outline" className="rounded-md">
      Active
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

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
      {filtered ? "No listings match the active search." : "No listings returned."}
    </p>
  )
}
