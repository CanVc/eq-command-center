import { describe, expect, it, vi } from "vitest"

import {
  buildApiPath,
  fetchDeals,
  fetchDashboardSummary,
  fetchHealth,
  fetchItemDetailPageData,
  fetchItemTooltip,
  fetchItemSearchPreview,
  fetchListingsPreview,
  fetchMarketListings,
  fetchSettingsStatus,
} from "./api"

describe("fetchHealth", () => {
  it("calls the health endpoint through the Vite proxy path", async () => {
    const payload = { status: "ok", db_path: "C:/tmp/eqmarket.sqlite" }
    const fetcher = vi.fn(async () => {
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    })

    await expect(fetchHealth(fetcher)).resolves.toEqual(payload)

    expect(fetcher).toHaveBeenCalledWith("/api/health", {
      headers: {
        Accept: "application/json",
      },
    })
  })

  it("raises an ApiError when the health endpoint is unavailable", async () => {
    const fetcher = vi.fn(async () => new Response("offline", { status: 503 }))

    await expect(fetchHealth(fetcher)).rejects.toEqual(
      expect.objectContaining({
        name: "ApiError",
        status: 503,
        message: "GET /api/health failed with 503",
      })
    )
  })
})

describe("page API helpers", () => {
  it("builds query strings without empty values", () => {
    expect(
      buildApiPath("/api/deals", {
        server: "frostreaver",
        limit: 5,
        q: undefined,
      })
    ).toBe("/api/deals?server=frostreaver&limit=5")
  })

  it("applies the active server to page requests", async () => {
    const fetcher = vi.fn(async () => {
      return new Response(JSON.stringify([]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    })

    await fetchDeals(
      "mischief",
      {
        minDiscount: 45,
        minPricePp: 5000,
        limit: 25,
        resolvedOnly: false,
      },
      fetcher
    )
    await fetchListingsPreview("mischief", fetcher)
    await fetchMarketListings("mischief", { query: " crown ", limit: 50 }, fetcher)
    await fetchItemSearchPreview("mischief", fetcher)

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/deals?server=mischief&min_discount=45&min_price_pp=5000&limit=25&resolved_only=false",
      {
        headers: {
          Accept: "application/json",
        },
      }
    )
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/listings/recent?server=mischief&limit=5", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(
      3,
      "/api/listings/recent?server=mischief&q=crown&limit=50",
      {
        headers: {
          Accept: "application/json",
        },
      }
    )
    expect(fetcher).toHaveBeenNthCalledWith(4, "/api/items/search?server=mischief&q=stave&limit=5", {
      headers: {
        Accept: "application/json",
      },
    })
  })

  it("fetches dashboard and settings status with the active server", async () => {
    const dashboardPayload = {
      server: "frostreaver",
      recent_window_hours: 24,
      min_discount: 30,
      listings_recent_count: 0,
      deals_recent_count: 0,
      krono_latest: {
        server: "frostreaver",
        price_pp: null,
        source: null,
        confidence: null,
        last_refresh_at: null,
      },
      top_seen_items: [],
      top_discounts: [],
    }
    const settingsPayload = {
      status: "ok",
      db_path: "C:/tmp/eqmarket.sqlite",
      default_server: "frostreaver",
      active_server: "frostreaver",
      latest_tlp_import: {
        import_run_id: 10,
        source_name: "tlp_auctions_prices",
        source_url: "server=frostreaver;mode=history;history_days=3",
        status: "completed",
        items_seen: 50,
        items_inserted: 2,
        items_updated: 12,
        error: null,
        started_at: "2026-06-16T09:59:00",
        finished_at: "2026-06-16T10:00:00",
      },
      import_runs_error: null,
    }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(dashboardPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(settingsPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )

    await expect(fetchDashboardSummary("frostreaver", fetcher)).resolves.toEqual(dashboardPayload)
    await expect(fetchSettingsStatus("frostreaver", fetcher)).resolves.toEqual(settingsPayload)

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/dashboard/summary?server=frostreaver&top_limit=5", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/settings/status?server=frostreaver", {
      headers: {
        Accept: "application/json",
      },
    })
  })

  it("fetches item tooltips by resolved id or fallback name", async () => {
    const tooltipPayload = {
      item_id: 1,
      name: "Stave of Shielding",
      icon_url: null,
      slot: "PRIMARY",
      classes: "WAR",
      races: "ALL",
      item_type: "weapon",
      flags: "MAGIC",
      server: "frostreaver",
      ac: 12,
      hp: 55,
      mana: 10,
      endurance: null,
      hp_regen: null,
      mana_regen: null,
      endurance_regen: null,
      str: 4,
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
      damage: 12,
      delay: 30,
      ratio: 0.4,
      haste: null,
      required_level: null,
      recommended_level: null,
      market_price_pp: 16000,
      market_price_source: "median_pp",
      median_pp: 16000,
      p25_pp: 12000,
      p75_pp: 20000,
      avg_pp: 17000,
      sample_size: 12,
      confidence: "high",
      last_refresh_at: "2026-06-16T10:00:00",
      last_seen_pp: 4000,
      last_seen_at: "2026-06-16T10:00:00",
      last_seen_seller: "Nebblastin",
      last_seen_price_raw: "4k",
      effects: [],
    }
    const fetcher = vi.fn(async () => {
      return new Response(JSON.stringify(tooltipPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    })

    await expect(
      fetchItemTooltip({ itemId: 1, name: "Stave of Shielding", server: "frostreaver" }, fetcher)
    ).resolves.toEqual(tooltipPayload)
    await expect(
      fetchItemTooltip({ itemId: null, name: "Unidentified Idol", server: "mischief" }, fetcher)
    ).resolves.toEqual(tooltipPayload)

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/items/1/tooltip?server=frostreaver", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(
      2,
      "/api/items/tooltip?server=mischief&name=Unidentified+Idol",
      {
        headers: {
          Accept: "application/json",
        },
      }
    )
  })

  it("fetches item detail page data from item, price, listings, and Krono endpoints", async () => {
    const itemPayload = {
      item_id: 1,
      name: "Stave of Shielding",
      icon_url: null,
      icon_id: 601,
      item_type: "weapon",
      slot: "PRIMARY",
      classes: "WAR PAL",
      races: "ALL",
      flags: "MAGIC",
      stats: {
        ac: 12,
        hp: 55,
        mana: 10,
        endurance: null,
        hp_regen: null,
        mana_regen: null,
        endurance_regen: null,
        str: 4,
        sta: 5,
        agi: 6,
        dex: 7,
        wis: 8,
        int: 9,
        cha: 10,
        heroic_str: null,
        heroic_sta: null,
        heroic_agi: null,
        heroic_dex: null,
        heroic_wis: null,
        heroic_int: null,
        heroic_cha: null,
        sv_magic: 11,
        sv_fire: 12,
        sv_cold: 13,
        sv_poison: 14,
        sv_disease: 15,
      },
      combat: {
        damage: 12,
        delay: 30,
        ratio: 0.4,
        haste: null,
      },
      levels: {
        required_level: null,
        recommended_level: 50,
      },
      effects: [],
      source_primary: "fixture",
      last_imported_at: "2026-06-16T09:00:00",
    }
    const pricePayload = {
      item_id: 1,
      server: "mischief",
      market_price_pp: 16000,
      market_price_source: "median_pp",
      median_pp: 16000,
      p25_pp: 12000,
      p75_pp: 20000,
      avg_pp: 17000,
      min_pp: 10000,
      max_pp: 24000,
      sample_size: 12,
      confidence: "high",
      last_refresh_at: "2026-06-16T10:00:00",
      source: "fixture",
    }
    const listingsPayload = [
      {
        listing_id: 10,
        timestamp: "2026-06-16T10:00:00",
        seller: "Nebblastin",
        item: { item_id: 1, name: "Stave of Shielding" },
        item_id: 1,
        item_name: "Stave of Shielding",
        listed_item_name: "Stave of Shielding MQ",
        price_raw: "4k",
        price_pp: 4000,
        source: "eq_log",
        confidence: "parsed",
        resolved: true,
      },
    ]
    const kronoPayload = {
      server: "mischief",
      price_pp: 16000,
      source: "fixture",
      confidence: "high",
      last_refresh_at: "2026-06-16T10:00:00",
    }
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = new URL(String(input), "http://frontend.test")

      if (url.pathname === "/api/items/1") {
        return jsonResponse(itemPayload)
      }

      if (url.pathname === "/api/items/1/prices") {
        return jsonResponse(pricePayload)
      }

      if (url.pathname === "/api/items/1/listings") {
        return jsonResponse(listingsPayload)
      }

      if (url.pathname === "/api/krono/latest") {
        return jsonResponse(kronoPayload)
      }

      return new Response("missing fixture", { status: 404 })
    })

    await expect(fetchItemDetailPageData(1, "mischief", fetcher)).resolves.toEqual({
      item: itemPayload,
      price: pricePayload,
      listings: listingsPayload,
      kronoLatest: kronoPayload,
    })

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/items/1", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/items/1/prices?server=mischief", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(3, "/api/items/1/listings?server=mischief&limit=100", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(4, "/api/krono/latest?server=mischief", {
      headers: {
        Accept: "application/json",
      },
    })
  })
})

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  })
}
