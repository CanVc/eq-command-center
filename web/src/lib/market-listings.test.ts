import { describe, expect, it } from "vitest"

import {
  canLoadMoreListings,
  expandMarketListingLimit,
  normalizeMarketListingFilters,
  resetMarketListingSearch,
} from "@/lib/market-listings"

describe("market listing filters", () => {
  it("normalizes search input and resets pagination", () => {
    expect(resetMarketListingSearch("  Neb   blastin  ")).toEqual({
      query: "Neb blastin",
      reviewStatus: "active",
      interestStatus: "tracked",
      limit: 25,
    })
  })

  it("expands and clamps listing limits", () => {
    expect(expandMarketListingLimit({ query: "stave", reviewStatus: "discarded", interestStatus: "ignored", limit: 25 })).toEqual({
      query: "stave",
      reviewStatus: "discarded",
      interestStatus: "ignored",
      limit: 50,
    })

    expect(expandMarketListingLimit({ query: "stave", reviewStatus: "discarded", interestStatus: "ignored", limit: 490 })).toEqual({
      query: "stave",
      reviewStatus: "discarded",
      interestStatus: "ignored",
      limit: 500,
    })
  })

  it("keeps API filters in supported ranges", () => {
    expect(normalizeMarketListingFilters({ query: " crown ", reviewStatus: "all", interestStatus: "wanted", limit: Number.NaN })).toEqual({
      query: "crown",
      reviewStatus: "all",
      interestStatus: "wanted",
      limit: 25,
    })

    expect(normalizeMarketListingFilters({ query: "", reviewStatus: "active", interestStatus: "tracked", limit: -5 })).toEqual({
      query: "",
      reviewStatus: "active",
      interestStatus: "tracked",
      limit: 1,
    })
  })

  it("only offers load more when the current page may be full", () => {
    expect(canLoadMoreListings(25, 25)).toBe(true)
    expect(canLoadMoreListings(24, 25)).toBe(false)
    expect(canLoadMoreListings(500, 500)).toBe(false)
  })
})
