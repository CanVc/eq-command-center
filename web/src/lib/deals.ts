import type { DealFilters, DealPreview } from "@/lib/api"
import { DEFAULT_DEAL_FILTERS } from "@/lib/api"
import { formatPrice } from "@/lib/format"

export type DraftDealFilters = {
  minDiscount: string
  minPricePp: string
  limit: string
  resolvedOnly: boolean
}

export function buildTellMessage(
  deal: Pick<DealPreview, "seller" | "item_name" | "price_raw" | "listing_price_pp">
): string {
  return `/tell ${deal.seller ?? "Unknown"} Hi, still selling ${deal.item_name} for ${
    deal.price_raw ?? formatPrice(deal.listing_price_pp)
  }?`
}

export function normalizeDealFilters(filters: DraftDealFilters): DealFilters {
  return {
    minDiscount: clampNumber(filters.minDiscount, DEFAULT_DEAL_FILTERS.minDiscount, 0, 100),
    minPricePp: clampNumber(filters.minPricePp, DEFAULT_DEAL_FILTERS.minPricePp, 0, 10_000_000),
    limit: Math.round(clampNumber(filters.limit, DEFAULT_DEAL_FILTERS.limit, 1, 500)),
    resolvedOnly: filters.resolvedOnly,
  }
}

export function dealFiltersToDraft(filters: DealFilters): DraftDealFilters {
  return {
    minDiscount: String(filters.minDiscount),
    minPricePp: String(filters.minPricePp),
    limit: String(filters.limit),
    resolvedOnly: filters.resolvedOnly,
  }
}

export function dealFiltersKey(filters: DealFilters): string {
  return [
    filters.minDiscount,
    filters.minPricePp,
    filters.limit,
    filters.resolvedOnly ? "resolved" : "all",
  ].join(":")
}

export function discountBadgeClassName(value: number): string {
  if (value >= 70) {
    return "border-red-500/25 bg-red-500/10 text-red-700 dark:text-red-300"
  }

  if (value >= 50) {
    return "border-amber-500/25 bg-amber-500/10 text-amber-700 dark:text-amber-300"
  }

  return "border-emerald-500/25 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
}

function clampNumber(value: string, fallback: number, min: number, max: number): number {
  if (value.trim() === "") {
    return fallback
  }

  const parsedValue = Number(value)

  if (!Number.isFinite(parsedValue)) {
    return fallback
  }

  return Math.min(Math.max(parsedValue, min), max)
}
