import {
  DEFAULT_MARKET_LISTING_FILTERS,
  MARKET_LISTING_PAGE_SIZE,
  type ItemInterestFilter,
  type ListingReviewStatusFilter,
  type MarketListingFilters,
} from "@/lib/api"

const MAX_MARKET_LISTING_LIMIT = 500

export function resetMarketListingSearch(
  query: string,
  reviewStatus: ListingReviewStatusFilter = DEFAULT_MARKET_LISTING_FILTERS.reviewStatus,
  interestStatus: ItemInterestFilter = DEFAULT_MARKET_LISTING_FILTERS.interestStatus
): MarketListingFilters {
  return {
    ...DEFAULT_MARKET_LISTING_FILTERS,
    query: normalizeListingQuery(query),
    reviewStatus: normalizeReviewStatus(reviewStatus),
    interestStatus: normalizeInterestStatus(interestStatus),
  }
}

export function expandMarketListingLimit(filters: MarketListingFilters): MarketListingFilters {
  return normalizeMarketListingFilters({
    ...filters,
    limit: filters.limit + MARKET_LISTING_PAGE_SIZE,
  })
}

export function normalizeMarketListingFilters(filters: MarketListingFilters): MarketListingFilters {
  return {
    query: normalizeListingQuery(filters.query),
    reviewStatus: normalizeReviewStatus(filters.reviewStatus),
    interestStatus: normalizeInterestStatus(filters.interestStatus),
    limit: clampLimit(filters.limit),
  }
}

export function canLoadMoreListings(rowCount: number, limit: number): boolean {
  return rowCount >= limit && limit < MAX_MARKET_LISTING_LIMIT
}

export function marketListingFiltersKey(filters: MarketListingFilters): string {
  return `${filters.query}\u0000${filters.reviewStatus}\u0000${filters.interestStatus}\u0000${filters.limit}`
}

function normalizeListingQuery(query: string): string {
  return query.trim().replace(/\s+/g, " ")
}

function normalizeReviewStatus(status: ListingReviewStatusFilter): ListingReviewStatusFilter {
  return ["active", "suspect", "discarded", "all"].includes(status) ? status : DEFAULT_MARKET_LISTING_FILTERS.reviewStatus
}

function normalizeInterestStatus(status: ItemInterestFilter): ItemInterestFilter {
  return ["tracked", "wanted", "ignored", "all"].includes(status) ? status : DEFAULT_MARKET_LISTING_FILTERS.interestStatus
}

function clampLimit(limit: number): number {
  if (!Number.isFinite(limit)) {
    return DEFAULT_MARKET_LISTING_FILTERS.limit
  }

  return Math.min(MAX_MARKET_LISTING_LIMIT, Math.max(1, Math.trunc(limit)))
}
