import { describe, expect, it, vi } from "vitest"

import {
  browseEqLogPath,
  buildApiPath,
  fetchDeals,
  fetchDashboardSummary,
  fetchHealth,
  fetchInterfacePageData,
  fetchItemDetailPageData,
  fetchItemTooltip,
  fetchItemSearchPreview,
  fetchListingsPreview,
  fetchMarketListings,
  fetchRuntimeStatus,
  fetchSettingsStatus,
  discardListing,
  discardSimilarListings,
  markTlpPricesStale,
  refreshKronoPrice,
  refreshTlpPrices,
  startTlpPriceRefreshJob,
  fetchTlpPriceRefreshJob,
  restoreSimilarListings,
  updateEqLogPath,
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
        includeSuspect: true,
      },
      fetcher
    )
    await fetchListingsPreview("mischief", fetcher)
    await fetchMarketListings("mischief", { query: " crown ", reviewStatus: "discarded", limit: 50 }, fetcher)
    await fetchItemSearchPreview("mischief", fetcher)
    await fetchRuntimeStatus("mischief", 90, fetcher)

    expect(fetcher).toHaveBeenNthCalledWith(
      1,
      "/api/deals?server=mischief&min_discount=45&min_price_pp=5000&limit=25&resolved_only=false&include_suspect=true",
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
      "/api/listings/recent?server=mischief&q=crown&review_status=discarded&limit=50",
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
    expect(fetcher).toHaveBeenNthCalledWith(5, "/api/runtime/status?server=mischief&max_age_minutes=90", {
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
      eq_log_path: "C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt",
      eq_log_exists: true,
      eq_log_import_state: null,
      log_settings_error: null,
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

  it("fetches interface diagnostics and marks TLP prices stale", async () => {
    const tlpPayload = {
      server: "frostreaver",
      max_age_minutes: 360,
      max_age_hours: 6,
      stale_item_count: 2,
      latest_tlp_import: null,
      active_errors: [],
      active_error_count: 0,
    }
    const logPayload = {
      server: "frostreaver",
      issues: [],
      issue_count: 0,
      limit: 500,
    }
    const stalePayload = {
      server: "frostreaver",
      affected_count: 4,
    }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(tlpPayload))
      .mockResolvedValueOnce(jsonResponse(logPayload))
      .mockResolvedValueOnce(jsonResponse(stalePayload))

    await expect(fetchInterfacePageData("frostreaver", 360, fetcher)).resolves.toEqual({
      tlpErrors: tlpPayload,
      logParseIssues: logPayload,
    })
    await expect(markTlpPricesStale("frostreaver", fetcher)).resolves.toEqual(stalePayload)

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/interface/tlp-errors?server=frostreaver&max_age_minutes=360", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/interface/log-parse-issues?server=frostreaver", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(3, "/api/interface/tlp-prices/mark-stale?server=frostreaver", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    })
  })

  it("discards listing reviews", async () => {
    const payload = {
      listing_id: 42,
      server: "frostreaver",
      status: "discarded",
      reason_code: "wrong_unit",
      note: null,
      created_at: "2026-06-18 12:00:00",
      updated_at: "2026-06-18 12:00:00",
    }
    const fetcher = vi.fn().mockResolvedValue(jsonResponse(payload))

    await expect(discardListing(42, "wrong_unit", null, fetcher)).resolves.toEqual(payload)

    expect(fetcher).toHaveBeenCalledWith("/api/listings/42/review", {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ status: "discarded", reason_code: "wrong_unit", note: null }),
    })
  })

  it("posts similar review rule actions", async () => {
    const payload = {
      listing_id: 42,
      server: "frostreaver",
      action: "discard_similar",
      matched_count: 3,
      review: {
        listing_id: 42,
        server: "frostreaver",
        status: "discarded",
        reason_code: "manual",
        note: null,
        created_at: "2026-06-18 12:00:00",
        updated_at: "2026-06-18 12:00:00",
      },
    }
    const restorePayload = { ...payload, action: "restore_similar", disabled_rule_count: 1, restored_count: 3 }
    const fetcher = vi.fn()
      .mockResolvedValueOnce(jsonResponse(payload))
      .mockResolvedValueOnce(jsonResponse(restorePayload))

    await expect(discardSimilarListings(42, "manual", null, fetcher)).resolves.toEqual(payload)
    await restoreSimilarListings(42, fetcher)

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/listings/42/discard-similar", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ reason_code: "manual", note: null }),
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/listings/42/restore-similar", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    })
  })

  it("posts manual TLP refresh requests", async () => {
    const kronoPayload = {
      server: "frostreaver",
      krono_updated: true,
      krono_price_pp: 17463,
      krono_listings_converted: 3,
    }
    const jobPayload = {
      job_id: "abc123",
      server: "frostreaver",
      status: "running",
      phase: "history",
      completed: 5,
      total: 10,
      current_item_id: 123,
      target_item_ids: [1, 2],
      target_count: 2,
      limit: 500,
      max_age_hours: 6,
      max_age_minutes: 360,
      history_days: 3,
      concurrency: 10,
      stats: null,
      error: null,
      created_at: "2026-06-16T09:59:00Z",
      started_at: "2026-06-16T10:00:00Z",
      finished_at: null,
    }
    const pricePayload = {
      server: "frostreaver",
      target_item_ids: [1, 2],
      target_count: 2,
      limit: 500,
      max_age_hours: 6,
      max_age_minutes: 360,
      history_days: 3,
      concurrency: 10,
      catalog_items_seen: 10,
      items_upserted: 0,
      listings_linked: 1,
      catalog_prices_upserted: 0,
      history_items_checked: 2,
      history_prices_upserted: 2,
      no_price_data: 0,
      price_refresh_failed: 0,
      krono_updated: true,
      krono_price_pp: 17463,
      krono_listings_converted: 3,
    }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(kronoPayload))
      .mockResolvedValueOnce(jsonResponse(jobPayload))
      .mockResolvedValueOnce(jsonResponse(jobPayload))
      .mockResolvedValueOnce(jsonResponse(pricePayload))
      .mockResolvedValueOnce(jsonResponse(jobPayload))

    await expect(refreshKronoPrice("frostreaver", fetcher)).resolves.toEqual(kronoPayload)
    await expect(startTlpPriceRefreshJob("frostreaver", { maxAgeMinutes: 360 }, fetcher)).resolves.toEqual(jobPayload)
    await expect(fetchTlpPriceRefreshJob("abc123", fetcher)).resolves.toEqual(jobPayload)
    await expect(refreshTlpPrices("frostreaver", { maxAgeMinutes: 360 }, fetcher)).resolves.toEqual(pricePayload)
    await expect(
      startTlpPriceRefreshJob("frostreaver", { maxAgeMinutes: 360, refreshKronoWhenEmpty: false }, fetcher)
    ).resolves.toEqual(jobPayload)

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/krono/refresh?server=frostreaver", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/tlp-prices/refresh-jobs?server=frostreaver&max_age_minutes=360", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(3, "/api/tlp-prices/refresh-jobs/abc123", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(4, "/api/tlp-prices/refresh?server=frostreaver&max_age_minutes=360", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(
      5,
      "/api/tlp-prices/refresh-jobs?server=frostreaver&max_age_minutes=360&refresh_krono_when_empty=false",
      {
        method: "POST",
        headers: {
          Accept: "application/json",
        },
      }
    )
  })

  it("updates the configured EQ log path", async () => {
    const payload = {
      eq_log_path: "C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt",
      eq_log_exists: true,
      eq_log_import_state: null,
      log_settings_error: null,
    }
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )

    await expect(
      updateEqLogPath("frostreaver", "C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt", fetcher)
    ).resolves.toEqual(payload)

    expect(fetcher).toHaveBeenCalledWith("/api/settings/log-path?server=frostreaver", {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ log_path: "C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt" }),
    })
  })

  it("opens the backend native picker for the EQ log path", async () => {
    const payload = {
      eq_log_path: "C:/EverQuest/Logs/eqlog_Browse_frostreaver.txt",
      eq_log_exists: true,
      eq_log_import_state: null,
      log_settings_error: null,
    }
    const fetcher = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    )

    await expect(browseEqLogPath("frostreaver", fetcher)).resolves.toEqual(payload)

    expect(fetcher).toHaveBeenCalledWith("/api/settings/log-path/browse?server=frostreaver", {
      method: "POST",
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
    const tlpHistoryPayload = [
      {
        timestamp: "2026-06-01T10:00:00Z",
        price_pp: 50000,
        plat_price: 50000,
        krono_price: 0,
        krono_price_pp_used: null,
        seller: "Auctioneer",
        source: "tlp_auctions_history",
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

      if (url.pathname === "/api/tlp-prices/items/1/refresh") {
        return jsonResponse({
          server: "mischief",
          target_item_ids: [1],
          target_count: 1,
          limit: 1,
          max_age_hours: null,
          max_age_minutes: null,
          history_days: 3,
          concurrency: 1,
          catalog_items_seen: 1,
          items_upserted: 0,
          listings_linked: 0,
          catalog_prices_upserted: 0,
          history_items_checked: 1,
          history_prices_upserted: 1,
          no_price_data: 0,
          price_refresh_failed: 0,
          krono_updated: true,
          krono_price_pp: 16000,
          krono_listings_converted: 0,
        })
      }

      if (url.pathname === "/api/items/1") {
        return jsonResponse(itemPayload)
      }

      if (url.pathname === "/api/items/1/prices") {
        return jsonResponse(pricePayload)
      }

      if (url.pathname === "/api/items/1/listings") {
        return jsonResponse(listingsPayload)
      }

      if (url.pathname === "/api/items/1/tlp-history") {
        return jsonResponse(tlpHistoryPayload)
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
      tlpHistory: tlpHistoryPayload,
      kronoLatest: kronoPayload,
    })

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/tlp-prices/items/1/refresh?server=mischief", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/items/1", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(3, "/api/items/1/prices?server=mischief", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(4, "/api/items/1/listings?server=mischief&limit=100", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(5, "/api/items/1/tlp-history?server=mischief", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(6, "/api/krono/latest?server=mischief", {
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
