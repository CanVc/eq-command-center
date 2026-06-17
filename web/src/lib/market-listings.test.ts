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
      limit: 25,
    })
  })

  it("expands and clamps listing limits", () => {
    expect(expandMarketListingLimit({ query: "stave", limit: 25 })).toEqual({
      query: "stave",
      limit: 50,
    })

    expect(expandMarketListingLimit({ query: "stave", limit: 490 })).toEqual({
      query: "stave",
      limit: 500,
    })
  })

  it("keeps API filters in supported ranges", () => {
    expect(normalizeMarketListingFilters({ query: " crown ", limit: Number.NaN })).toEqual({
      query: "crown",
      limit: 25,
    })

    expect(normalizeMarketListingFilters({ query: "", limit: -5 })).toEqual({
      query: "",
      limit: 1,
    })
  })

  it("only offers load more when the current page may be full", () => {
    expect(canLoadMoreListings(25, 25)).toBe(true)
    expect(canLoadMoreListings(24, 25)).toBe(false)
    expect(canLoadMoreListings(500, 500)).toBe(false)
  })
})
