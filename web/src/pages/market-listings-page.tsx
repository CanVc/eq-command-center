import { ListPlus, Search, X } from "lucide-react"
import { useState } from "react"
import type { FormEvent } from "react"

import { ItemLink } from "@/components/item-link"
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
import type { ListingPreview, MarketListingFilters } from "@/lib/api"
import { formatDateTime, formatPrice } from "@/lib/format"
import {
  canLoadMoreListings,
  expandMarketListingLimit,
  resetMarketListingSearch,
} from "@/lib/market-listings"
import { cn } from "@/lib/utils"

type MarketListingsPageProps = {
  listings: ListingPreview[]
  filters: MarketListingFilters
  onFiltersChange: (filters: MarketListingFilters) => void
}

const searchInputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function MarketListingsPage({
  listings,
  filters,
  onFiltersChange,
}: MarketListingsPageProps) {
  const [draftQuery, setDraftQuery] = useState(filters.query)
  const canLoadMore = canLoadMoreListings(listings.length, filters.limit)

  const applySearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    onFiltersChange(resetMarketListingSearch(draftQuery))
  }

  const clearSearch = () => {
    setDraftQuery("")
    onFiltersChange(resetMarketListingSearch(""))
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
        className="grid gap-3 rounded-lg border bg-card p-3 sm:grid-cols-[minmax(0,1fr)_auto]"
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

      {listings.length > 0 ? <ListingsTable listings={listings} /> : <EmptyState filtered={!!filters.query} />}

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

function ListingsTable({ listings }: { listings: ListingPreview[] }) {
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
          </TableRow>
        </TableHeader>
        <TableBody>
          {listings.map((listing) => (
            <TableRow key={listing.listing_id}>
              <TableCell className="min-w-[10rem]">
                <time dateTime={listing.timestamp}>{formatDateTime(listing.timestamp)}</time>
              </TableCell>
              <TableCell>{listing.seller ?? "Unknown"}</TableCell>
              <TableCell className="min-w-[14rem] whitespace-normal">
                <ItemLink
                  itemId={listing.item_id}
                  name={listing.item_name}
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
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
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
          : "border-amber-500/40 bg-amber-500/10 text-amber-700"
      )}
    >
      {resolved ? "Resolved" : "Pending"}
    </Badge>
  )
}

function EmptyState({ filtered }: { filtered: boolean }) {
  return (
    <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
      {filtered ? "No listings match the active search." : "No listings returned."}
    </p>
  )
}
