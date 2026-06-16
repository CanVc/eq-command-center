import { describe, expect, it } from "vitest"

import {
  buildTellMessage,
  discountBadgeClassName,
  normalizeDealFilters,
} from "@/lib/deals"

describe("DealsPage helpers", () => {
  it("builds the tell command from seller, item, and raw price", () => {
    expect(
      buildTellMessage({
        seller: "Nebblastin",
        item_name: "Stave of Shielding",
        price_raw: "4k",
        listing_price_pp: 4000,
      })
    ).toBe("/tell Nebblastin Hi, still selling Stave of Shielding for 4k?")
  })

  it("falls back to formatted platinum when the raw price is absent", () => {
    expect(
      buildTellMessage({
        seller: null,
        item_name: "Fungi Covered Great Staff",
        price_raw: null,
        listing_price_pp: 12000,
      })
    ).toBe("/tell Unknown Hi, still selling Fungi Covered Great Staff for 12,000pp?")
  })

  it("normalizes numeric filters to API-safe ranges", () => {
    expect(
      normalizeDealFilters({
        minDiscount: "125",
        minPricePp: "-50",
        limit: "750",
        resolvedOnly: false,
      })
    ).toEqual({
      minDiscount: 100,
      minPricePp: 0,
      limit: 500,
      resolvedOnly: false,
    })

    expect(
      normalizeDealFilters({
        minDiscount: "",
        minPricePp: "not-a-number",
        limit: "",
        resolvedOnly: true,
      })
    ).toEqual({
      minDiscount: 30,
      minPricePp: 0,
      limit: 100,
      resolvedOnly: true,
    })
  })

  it("assigns distinct badge tones by discount strength", () => {
    expect(discountBadgeClassName(75)).toContain("red")
    expect(discountBadgeClassName(55)).toContain("amber")
    expect(discountBadgeClassName(35)).toContain("emerald")
  })
})
