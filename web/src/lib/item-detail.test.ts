import { describe, expect, it } from "vitest"

import type { ItemDetail, ItemListing } from "./api"
import {
  buildExternalItemLinks,
  buildPriceHistory,
  buildTlpPriceHistory,
  formatKronoEquivalent,
  latestPricedListing,
} from "./item-detail"

describe("item detail helpers", () => {
  it("builds chart history from local priced listings in chronological order", () => {
    const listings = [
      buildListing({ listing_id: 3, timestamp: "2026-06-16T12:00:00", price_pp: null }),
      buildListing({ listing_id: 2, timestamp: "2026-06-16T11:00:00", price_pp: 42000 }),
      buildListing({ listing_id: 1, timestamp: "2026-06-16T10:00:00", price_pp: 50000 }),
    ]

    expect(buildPriceHistory(listings)).toEqual([
      {
        sourceId: "listing:1",
        timestamp: "2026-06-16T10:00:00",
        price_pp: 50000,
        price_raw: "50000pp",
        seller: "Seller 1",
        source: "eq_log",
      },
      {
        sourceId: "listing:2",
        timestamp: "2026-06-16T11:00:00",
        price_pp: 42000,
        price_raw: "42000pp",
        seller: "Seller 2",
        source: "eq_log",
      },
    ])
  })

  it("builds chart history from full TLP sell points in chronological order", () => {
    expect(
      buildTlpPriceHistory([
        {
          timestamp: "2026-06-16T12:00:00Z",
          price_pp: 42000,
          plat_price: 10000,
          krono_price: 2,
          krono_price_pp_used: 16000,
          seller: "Seller Two",
          source: "tlp_auctions_history",
        },
        {
          timestamp: "2026-06-01T10:00:00Z",
          price_pp: 50000,
          plat_price: 50000,
          krono_price: 0,
          krono_price_pp_used: null,
          seller: "Seller One",
          source: "tlp_auctions_history",
        },
      ])
    ).toEqual([
      {
        sourceId: "tlp:2026-06-01T10:00:00Z:1",
        timestamp: "2026-06-01T10:00:00Z",
        price_pp: 50000,
        price_raw: "50000pp",
        seller: "Seller One",
        source: "tlp_auctions_history",
      },
      {
        sourceId: "tlp:2026-06-16T12:00:00Z:0",
        timestamp: "2026-06-16T12:00:00Z",
        price_pp: 42000,
        price_raw: "2 krono + 10000pp",
        seller: "Seller Two",
        source: "tlp_auctions_history",
      },
    ])
  })

  it("finds the latest priced local listing", () => {
    const listings = [
      buildListing({ listing_id: 1, timestamp: "2026-06-16T10:00:00", price_pp: 50000 }),
      buildListing({ listing_id: 2, timestamp: "2026-06-16T12:00:00", price_pp: null }),
      buildListing({ listing_id: 3, timestamp: "2026-06-16T11:00:00", price_pp: 42000 }),
    ]

    expect(latestPricedListing(listings)?.listing_id).toBe(3)
  })

  it("formats Krono equivalents only when both prices are usable", () => {
    expect(formatKronoEquivalent(32000, 16000)).toBe("2.00 Krono")
    expect(formatKronoEquivalent(250000, 16000)).toBe("15.6 Krono")
    expect(formatKronoEquivalent(null, 16000)).toBe("n/a")
    expect(formatKronoEquivalent(32000, 0)).toBe("n/a")
  })

  it("constructs external source links from the item record", () => {
    const item = buildItem({ item_id: 10895, name: "Stave of Shielding" })

    expect(buildExternalItemLinks(item, "Frostreaver")).toEqual([
      {
        label: "Lucy",
        href: "https://lucy.allakhazam.com/item.html?id=10895",
      },
      {
        label: "Magelo",
        href: "https://eq.magelo.com/item/10895",
      },
      {
        label: "TLP Auctions",
        href: "https://www.tlp-auctions.com/search/frostreaver/Stave%20of%20Shielding",
      },
    ])
  })
})

function buildListing(overrides: Partial<ItemListing>): ItemListing {
  const listingId = overrides.listing_id ?? 1

  return {
    listing_id: listingId,
    timestamp: overrides.timestamp ?? "2026-06-16T10:00:00",
    seller: overrides.seller ?? `Seller ${listingId}`,
    item: {
      item_id: 10895,
      name: "Stave of Shielding",
    },
    item_id: 10895,
    item_name: "Stave of Shielding",
    listed_item_name: "Stave of Shielding",
    price_raw: overrides.price_raw ?? `${overrides.price_pp ?? 0}pp`,
    raw_line: overrides.raw_line ?? "[Tue Jun 16 10:00:00 2026] Seller auctions, 'WTS Stave of Shielding 1000pp'",
    price_pp: overrides.price_pp ?? 1000,
    source: "eq_log",
    confidence: "parsed",
    resolved: true,
    review_status: "active",
    review_reason_code: null,
    review_note: null,
    ...overrides,
  }
}

function buildItem(overrides: Partial<ItemDetail>): ItemDetail {
  return {
    item_id: 10895,
    name: "Stave of Shielding",
    icon_url: null,
    icon_id: null,
    item_type: "weapon",
    slot: "PRIMARY",
    classes: "WAR PAL",
    races: "ALL",
    flags: "MAGIC",
    stats: {
      ac: null,
      hp: null,
      mana: null,
      endurance: null,
      hp_regen: null,
      mana_regen: null,
      endurance_regen: null,
      str: null,
      sta: null,
      agi: null,
      dex: null,
      wis: null,
      int: null,
      cha: null,
      heroic_str: null,
      heroic_sta: null,
      heroic_agi: null,
      heroic_dex: null,
      heroic_wis: null,
      heroic_int: null,
      heroic_cha: null,
      sv_magic: null,
      sv_fire: null,
      sv_cold: null,
      sv_poison: null,
      sv_disease: null,
    },
    combat: {
      damage: null,
      delay: null,
      ratio: null,
      haste: null,
    },
    levels: {
      required_level: null,
      recommended_level: null,
    },
    effects: [],
    source_primary: null,
    last_imported_at: null,
    ...overrides,
  }
}
