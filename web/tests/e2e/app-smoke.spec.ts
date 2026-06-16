import { expect, test, type Route } from "@playwright/test"

test("navigates main pages and stores the active server", async ({ page }) => {
  const requestedUrls: string[] = []

  await page.route("**/api/**", async (route) => {
    requestedUrls.push(route.request().url())
    await fulfillApi(route)
  })

  await page.goto("/")

  await expect(page).toHaveTitle(/EQ Command Center/)
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible()

  for (const label of ["Deals", "Market", "Items", "Settings"]) {
    await page.getByRole("link", { name: label }).click()
    await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible()
  }

  await page.getByRole("combobox", { name: "Server" }).click()
  await page.getByRole("option", { name: "Mischief" }).click()
  await expect(page.getByRole("combobox", { name: "Server" })).toContainText("Mischief")

  await page.getByRole("link", { name: "Dashboard" }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect.poll(() => requestedUrls.some((url) => hasServerParam(url, "mischief"))).toBe(true)

  const storedServer = await page.evaluate(() => localStorage.getItem("eq-command-center.server"))
  expect(storedServer).toBe("mischief")
})

test("renders dashboard summary cards, trends, and item popovers", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await fulfillApi(route)
  })

  await page.goto("/")

  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Server Overview" })).toBeVisible()
  await expect(page.getByText("Recent listings", { exact: true })).toBeVisible()
  await expect(page.getByText("Deals detected", { exact: true })).toBeVisible()
  await expect(page.getByText("Krono price", { exact: true })).toBeVisible()
  await expect(page.getByText("16,000pp").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Top Discounts" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Trends" })).toBeVisible()

  const itemLink = page.getByRole("link", { name: "Stave of Shielding" }).first()
  await expect(itemLink).toHaveAttribute("rel", "eq:item:1")
  await itemLink.click()

  const itemPopover = page.locator('[data-slot="hover-card-content"]')
  await expect(page.getByText("Item ID 1")).toBeVisible()
  await expect(itemPopover.getByText("Listed", { exact: true })).toBeVisible()
  await expect(itemPopover.getByText("Market", { exact: true })).toBeVisible()
})

test("keeps dashboard usable when summary lists and nullable metrics are empty", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/dashboard/summary") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(buildEmptyDashboardSummary(url.searchParams.get("server") ?? "frostreaver")),
      })
      return
    }

    await fulfillApi(route)
  })

  await page.goto("/")

  await expect(page.getByText("No qualifying discounts in the current window.")).toBeVisible()
  await expect(page.getByText("No item activity in the current window.")).toBeVisible()
  await expect(page.getByText("No Krono refresh found")).toBeVisible()
  await expect(page.getByText("n/a").first()).toBeVisible()
})

test("shows dashboard skeletons while the summary is loading", async ({ page }) => {
  let resolveDashboard: () => void = () => undefined
  const dashboardCanResolve = new Promise<void>((resolve) => {
    resolveDashboard = resolve
  })

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/dashboard/summary") {
      await dashboardCanResolve
    }

    await fulfillApi(route)
  })

  await page.goto("/")

  await expect(page.getByLabel("Dashboard loading")).toBeVisible()
  resolveDashboard()
  await expect(page.getByRole("heading", { name: "Server Overview" })).toBeVisible()
})

test("refresh relaunches the active page request without browser navigation", async ({ page }) => {
  let dashboardRequests = 0

  await page.route("**/api/**", async (route) => {
    if (new URL(route.request().url()).pathname === "/api/dashboard/summary") {
      dashboardRequests += 1
    }

    await fulfillApi(route)
  })

  await page.goto("/")
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible()
  await expect.poll(() => dashboardRequests).toBeGreaterThan(0)

  const pathnameBeforeRefresh = new URL(page.url()).pathname
  const requestCountBeforeRefresh = dashboardRequests

  await page.getByRole("button", { name: "Refresh" }).click()

  await expect.poll(() => dashboardRequests).toBeGreaterThan(requestCountBeforeRefresh)
  expect(new URL(page.url()).pathname).toBe(pathnameBeforeRefresh)
})

test("shows the shared error state when a page request fails", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/deals") {
      await route.fulfill({
        status: 503,
        contentType: "text/plain",
        body: "offline",
      })
      return
    }

    await fulfillApi(route)
  })

  await page.goto("/deals")

  await expect(page.getByText("Unable to load Deals")).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible()
})

async function fulfillApi(route: Route) {
  const url = new URL(route.request().url())
  const server = url.searchParams.get("server") ?? "frostreaver"

  if (url.pathname === "/api/health") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        db_path: "C:/Dev/Projects/eq-command-center/data/eqmarket.sqlite",
      }),
    })
    return
  }

  if (url.pathname === "/api/dashboard/summary") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildDashboardSummary(server)),
    })
    return
  }

  if (url.pathname === "/api/deals") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          listing_id: 10,
          timestamp: "2026-06-16T10:00:00",
          seller: "Nebblastin",
          item_id: 1,
          item_name: "Stave of Shielding",
          price_raw: "4k",
          listing_price_pp: 4000,
          market_price_pp: 16000,
          market_price_source: "median_pp",
          discount_pct: 75,
          potential_profit_pp: 12000,
          score: 4,
          deal_score: 4,
          sample_size: 12,
          confidence: "high",
          resolved: true,
        },
      ]),
    })
    return
  }

  if (url.pathname === "/api/listings/recent") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          listing_id: 20,
          timestamp: "2026-06-16T10:05:00",
          seller: "Aderyn",
          item_id: 2,
          item_name: "Silver Chitin Hand Wraps",
          price_raw: "8k",
          price_pp: 8000,
          source: "eq_log",
          confidence: "high",
          resolved: true,
        },
      ]),
    })
    return
  }

  if (url.pathname === "/api/items/search") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          item_id: 1,
          name: "Stave of Shielding",
          icon_url: null,
          slot: "PRIMARY",
          classes: "WAR CLR PAL RNG SHD DRU MNK BRD ROG SHM NEC WIZ MAG ENC BST BER",
          flags: "MAGIC",
        },
      ]),
    })
    return
  }

  await route.fulfill({
    status: 404,
    contentType: "text/plain",
    body: "unknown fixture endpoint",
  })
}

function hasServerParam(url: string, server: string): boolean {
  const parsedUrl = new URL(url)
  return parsedUrl.searchParams.get("server") === server
}

function buildDashboardSummary(server: string) {
  return {
    server,
    recent_window_hours: 24,
    min_discount: 30,
    listings_recent_count: 14,
    deals_recent_count: 2,
    krono_latest: {
      server,
      price_pp: 16000,
      source: "fixture",
      confidence: "high",
      last_refresh_at: "2026-06-16T10:00:00",
    },
    top_seen_items: [
      {
        item_id: 1,
        item_name: "Stave of Shielding",
        seen_count: 3,
        last_seen_at: "2026-06-16T10:00:00",
      },
    ],
    top_discounts: [
      {
        listing_id: 10,
        timestamp: "2026-06-16T10:00:00",
        seller: "Nebblastin",
        item_id: 1,
        item_name: "Stave of Shielding",
        price_raw: "4k",
        listing_price_pp: 4000,
        market_price_pp: 16000,
        market_price_source: "median_pp",
        discount_pct: 75,
        sample_size: 12,
        confidence: "high",
      },
    ],
  }
}

function buildEmptyDashboardSummary(server: string) {
  return {
    server,
    recent_window_hours: 24,
    min_discount: 30,
    listings_recent_count: 0,
    deals_recent_count: 0,
    krono_latest: {
      server,
      price_pp: null,
      source: null,
      confidence: null,
      last_refresh_at: null,
    },
    top_seen_items: [],
    top_discounts: [],
  }
}
