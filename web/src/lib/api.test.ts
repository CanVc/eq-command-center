import { describe, expect, it, vi } from "vitest"

import {
  buildApiPath,
  fetchDeals,
  fetchDashboardSummary,
  fetchHealth,
  fetchItemSearchPreview,
  fetchListingsPreview,
  fetchMarketListings,
  fetchSettingsHealth,
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

  it("fetches dashboard and settings with the active server", async () => {
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
    const healthPayload = { status: "ok", db_path: "C:/tmp/eqmarket.sqlite" }
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(dashboardPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(healthPayload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )

    await expect(fetchDashboardSummary("frostreaver", fetcher)).resolves.toEqual(dashboardPayload)
    await expect(fetchSettingsHealth("frostreaver", fetcher)).resolves.toEqual(healthPayload)

    expect(fetcher).toHaveBeenNthCalledWith(1, "/api/dashboard/summary?server=frostreaver&top_limit=5", {
      headers: {
        Accept: "application/json",
      },
    })
    expect(fetcher).toHaveBeenNthCalledWith(2, "/api/health?server=frostreaver", {
      headers: {
        Accept: "application/json",
      },
    })
  })
})
