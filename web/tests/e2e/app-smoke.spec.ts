import { expect, test, type Route } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.route("https://www.magelocdn.com/**", async (route) => {
    await route.abort()
  })
})

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
  await itemLink.hover()

  const itemPopover = page.locator('[data-slot="hover-card-content"]')
  await expect(page.getByText("Item ID 1")).toBeVisible()
  await expect(itemPopover.getByText("Stats", { exact: true })).toBeVisible()
  await expect(itemPopover.getByText("HP 55", { exact: false })).toBeVisible()
  await expect(itemPopover.getByText("Market price", { exact: true })).toBeVisible()
  await expect(itemPopover.getByText("16,000pp", { exact: true }).first()).toBeVisible()
})

test("uses the Magelo scanner when it is available", async ({ page }) => {
  const tooltipRequests: string[] = []

  await page.addInitScript(() => {
    const testWindow = window as Window & {
      __mageloScans?: number
      Magelobar?: { scan: () => void }
    }

    testWindow.Magelobar = {
      scan: () => {
        testWindow.__mageloScans = (testWindow.__mageloScans ?? 0) + 1
      },
    }
  })

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (isTooltipPath(url.pathname)) {
      tooltipRequests.push(url.toString())
    }

    await fulfillApi(route)
  })

  await page.goto("/")

  const itemLink = page.getByRole("link", { name: "Stave of Shielding" }).first()
  await expect(itemLink).toHaveAttribute("rel", "eq:item:1")
  await expect
    .poll(() => page.evaluate(() => (window as Window & { __mageloScans?: number }).__mageloScans ?? 0))
    .toBeGreaterThan(0)

  await itemLink.hover()
  await page.waitForTimeout(200)

  await expect(page.locator('[data-slot="hover-card-content"]')).toHaveCount(0)
  expect(tooltipRequests).toEqual([])
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

test("renders, filters, and acts on the deals table", async ({ page }) => {
  const dealRequests: URL[] = []
  const tooltipRequests: URL[] = []

  await page.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          ;(window as Window & { __copiedText?: string }).__copiedText = text
        },
      },
    })
  })

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/deals") {
      dealRequests.push(url)
    }

    if (isTooltipPath(url.pathname)) {
      tooltipRequests.push(url)
    }

    await fulfillApi(route)
  })

  await page.goto("/deals")

  await expect(page.getByRole("heading", { name: "Deals", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Deal Queue" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Seen price" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Market price" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Actions" })).toBeVisible()

  const rows = page.locator("tbody tr")
  await expect(rows.first()).toContainText("Manastone")
  await expect(page.getByRole("link", { name: "Stave of Shielding" })).toHaveAttribute(
    "rel",
    "eq:item:1"
  )

  await page.getByRole("link", { name: "Stave of Shielding" }).hover()
  await expect(page.getByText("Item ID 1")).toBeVisible()
  await expect(page.locator('[data-slot="hover-card-content"]').getByText("Market price")).toBeVisible()

  await page.getByRole("button", { name: "Copy tell for Stave of Shielding" }).click()
  await expect(page.getByRole("button", { name: "Copy tell for Stave of Shielding" })).toContainText(
    "Copied"
  )
  await expect
    .poll(() => page.evaluate(() => (window as Window & { __copiedText?: string }).__copiedText))
    .toBe("/tell Nebblastin Hi, still selling Stave of Shielding for 4k?")

  await page.getByLabel("Minimum discount").fill("80")
  await page.getByLabel("Minimum price").fill("2000")
  await page.getByLabel("Limit").fill("2")
  await page.getByLabel("Resolved only").uncheck()
  await page.getByRole("button", { name: "Apply" }).click()

  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("min_discount")).toBe("80")
  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("min_price_pp")).toBe("2000")
  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("limit")).toBe("2")
  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("resolved_only")).toBe("false")
  await expect(rows.first()).toContainText("Manastone")
  await expect(page.locator("tbody")).toContainText("Unidentified Idol")
  await expect(page.locator("tbody")).not.toContainText("Stave of Shielding")

  const unresolvedLink = page.getByRole("link", { name: "Unidentified Idol" })
  await expect(unresolvedLink).not.toHaveAttribute("rel", /eq:item:/)
  await unresolvedLink.hover()
  await expect(page.getByText("Item ID 99")).toBeVisible()
  await expect(page.locator('[data-slot="hover-card-content"]').getByText("Market price")).toBeVisible()
  await expect
    .poll(() =>
      tooltipRequests.some(
        (url) =>
          url.pathname === "/api/items/tooltip" &&
          url.searchParams.get("name") === "Unidentified Idol"
      )
    )
    .toBe(true)

  const requestCountBeforeRefresh = dealRequests.length
  await page.getByRole("button", { name: "Refresh" }).click()

  await expect.poll(() => dealRequests.length).toBeGreaterThan(requestCountBeforeRefresh)
  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("min_discount")).toBe("80")
  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("min_price_pp")).toBe("2000")

  const requestCountBeforeEmptyFilter = dealRequests.length

  await page.getByLabel("Minimum price").fill("999999")
  await page.getByRole("button", { name: "Apply" }).click()

  await expect.poll(() => dealRequests.length).toBeGreaterThan(requestCountBeforeEmptyFilter)
  await expect.poll(() => dealRequests.at(-1)?.searchParams.get("min_price_pp")).toBe("999999")
  await expect(page.getByText("No deals match the active filters.")).toBeVisible()
})

test("renders, searches, refreshes, and loads market listings", async ({ page }) => {
  const listingRequests: URL[] = []

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/listings/recent") {
      listingRequests.push(url)
    }

    await fulfillApi(route)
  })

  await page.goto("/market")

  await expect(page.getByRole("heading", { name: "Market", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Raw Listings" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Timestamp" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Price raw" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Price PP" })).toBeVisible()
  await expect(page.getByRole("columnheader", { name: "Status" })).toBeVisible()

  const tableBody = page.locator("tbody")
  await expect(tableBody.locator("tr").first()).toContainText("Unidentified Idol")
  await expect(page.getByText("Pending").first()).toBeVisible()
  await expect(page.getByText("Resolved").first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Stave of Shielding" })).toHaveAttribute(
    "rel",
    "eq:item:1"
  )
  await expect(tableBody).not.toContainText("Fine Steel Sword 27")
  await expect.poll(() => listingRequests.at(-1)?.searchParams.get("limit")).toBe("25")

  await page.getByRole("button", { name: "Load more" }).click()

  await expect.poll(() => listingRequests.at(-1)?.searchParams.get("limit")).toBe("50")
  await expect(tableBody).toContainText("Fine Steel Sword 27")

  await page.getByLabel("Search listings").fill("Nebblastin")
  await page.getByRole("button", { name: "Search" }).click()

  await expect.poll(() => listingRequests.at(-1)?.searchParams.get("q")).toBe("Nebblastin")
  await expect(tableBody).toContainText("Stave of Shielding")
  await expect(tableBody).not.toContainText("Unidentified Idol")

  await page.getByLabel("Search listings").fill("idol")
  await page.getByRole("button", { name: "Search" }).click()

  await expect.poll(() => listingRequests.at(-1)?.searchParams.get("q")).toBe("idol")
  await expect(tableBody).toContainText("Unidentified Idol")
  await expect(page.getByText("Pending").first()).toBeVisible()
  await expect(tableBody).not.toContainText("Stave of Shielding")

  const requestCountBeforeRefresh = listingRequests.length
  await page.getByRole("button", { name: "Refresh" }).click()

  await expect.poll(() => listingRequests.length).toBeGreaterThan(requestCountBeforeRefresh)
  await expect.poll(() => listingRequests.at(-1)?.searchParams.get("q")).toBe("idol")
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
      body: JSON.stringify(buildDeals(url)),
    })
    return
  }

  if (url.pathname === "/api/listings/recent") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildListings(url)),
    })
    return
  }

  if (url.pathname === "/api/items/tooltip") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        buildItemTooltip({
          itemId: 99,
          name: url.searchParams.get("name") ?? "Unidentified Item",
          server,
          marketPricePp: 14000,
          lastSeenPp: 2500,
        })
      ),
    })
    return
  }

  const tooltipItemId = itemTooltipIdFromPath(url.pathname)

  if (tooltipItemId !== null) {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        buildItemTooltip({
          itemId: tooltipItemId,
          name: tooltipItemName(tooltipItemId),
          server,
          marketPricePp: tooltipItemId === 1 ? 16000 : 10000,
          lastSeenPp: tooltipItemId === 1 ? 4000 : 8000,
        })
      ),
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

function isTooltipPath(pathname: string): boolean {
  return pathname === "/api/items/tooltip" || itemTooltipIdFromPath(pathname) !== null
}

function itemTooltipIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/api\/items\/(\d+)\/tooltip$/)
  return match ? Number(match[1]) : null
}

function hasServerParam(url: string, server: string): boolean {
  const parsedUrl = new URL(url)
  return parsedUrl.searchParams.get("server") === server
}

function tooltipItemName(itemId: number): string {
  if (itemId === 1) {
    return "Stave of Shielding"
  }

  if (itemId === 2) {
    return "Silver Chitin Hand Wraps"
  }

  if (itemId === 3) {
    return "Manastone"
  }

  return `Item ${itemId}`
}

function buildItemTooltip({
  itemId,
  name,
  server,
  marketPricePp,
  lastSeenPp,
}: {
  itemId: number
  name: string
  server: string
  marketPricePp: number
  lastSeenPp: number
}) {
  return {
    item_id: itemId,
    name,
    icon_url: null,
    slot: itemId === 1 ? "PRIMARY" : "ANY",
    classes: "WAR CLR PAL RNG SHD DRU MNK BRD ROG SHM NEC WIZ MAG ENC BST BER",
    races: "ALL",
    item_type: itemId === 1 ? "weapon" : "misc",
    flags: "MAGIC",
    server,
    ac: itemId === 1 ? 12 : 0,
    hp: itemId === 1 ? 55 : 10,
    mana: itemId === 1 ? 10 : 0,
    endurance: null,
    hp_regen: null,
    mana_regen: null,
    endurance_regen: null,
    str: itemId === 1 ? 4 : null,
    sta: itemId === 1 ? 5 : null,
    agi: itemId === 1 ? 6 : null,
    dex: itemId === 1 ? 7 : null,
    wis: itemId === 1 ? 8 : null,
    int: itemId === 1 ? 9 : null,
    cha: itemId === 1 ? 10 : null,
    heroic_str: null,
    heroic_sta: null,
    heroic_agi: null,
    heroic_dex: null,
    heroic_wis: null,
    heroic_int: null,
    heroic_cha: null,
    sv_magic: itemId === 1 ? 11 : null,
    sv_fire: itemId === 1 ? 12 : null,
    sv_cold: itemId === 1 ? 13 : null,
    sv_poison: itemId === 1 ? 14 : null,
    sv_disease: itemId === 1 ? 15 : null,
    damage: itemId === 1 ? 12 : null,
    delay: itemId === 1 ? 30 : null,
    ratio: itemId === 1 ? 0.4 : null,
    haste: null,
    required_level: null,
    recommended_level: itemId === 1 ? 50 : null,
    market_price_pp: marketPricePp,
    market_price_source: "median_pp",
    median_pp: marketPricePp,
    p25_pp: marketPricePp - 1000,
    p75_pp: marketPricePp + 1000,
    avg_pp: marketPricePp,
    sample_size: 12,
    confidence: "high",
    last_refresh_at: "2026-06-16T10:00:00",
    last_seen_pp: lastSeenPp,
    last_seen_at: "2026-06-16T10:00:00",
    last_seen_seller: "Nebblastin",
    last_seen_price_raw: `${lastSeenPp}pp`,
    effects: [
      {
        effect_slot: 0,
        trigger_type: "worn",
        effect_type_raw: 1,
        spell: {
          spell_id: 1806,
          name: "Fungal Regrowth",
          spell_type: "Beneficial",
          target_type: "Self",
          skill: "Alteration",
        },
        cast_time_ms: 0,
        required_level: null,
        effective_level: 0,
        proc_rate: null,
        charges: null,
        description: "Fungal Regrowth",
      },
    ],
  }
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

function buildDeals(url: URL) {
  const minDiscount = Number(url.searchParams.get("min_discount") ?? "30")
  const minPricePp = Number(url.searchParams.get("min_price_pp") ?? "0")
  const limit = Number(url.searchParams.get("limit") ?? "100")
  const resolvedOnly = url.searchParams.get("resolved_only") !== "false"

  return [
    {
      listing_id: 12,
      timestamp: "2026-06-16T10:10:00",
      seller: "Bazzarbot",
      item: { item_id: 3, name: "Manastone" },
      item_id: 3,
      item_name: "Manastone",
      price_raw: "3k",
      listing_price_pp: 3000,
      market_price_pp: 20000,
      market_price_source: "median_pp",
      discount_pct: 85,
      potential_profit_pp: 17000,
      score: 95.5,
      deal_score: 95.5,
      sample_size: 8,
      confidence: "high",
      resolved: true,
    },
    {
      listing_id: 13,
      timestamp: "2026-06-16T10:15:00",
      seller: "Mystery",
      item: { item_id: null, name: "Unidentified Idol" },
      item_id: null,
      item_name: "Unidentified Idol",
      price_raw: "2500pp",
      listing_price_pp: 2500,
      market_price_pp: 14000,
      market_price_source: "avg_pp",
      discount_pct: 82.14,
      potential_profit_pp: 11500,
      score: 82.14,
      deal_score: 82.14,
      sample_size: 3,
      confidence: "medium",
      resolved: false,
    },
    {
      listing_id: 10,
      timestamp: "2026-06-16T10:00:00",
      seller: "Nebblastin",
      item: { item_id: 1, name: "Stave of Shielding" },
      item_id: 1,
      item_name: "Stave of Shielding",
      price_raw: "4k",
      listing_price_pp: 4000,
      market_price_pp: 16000,
      market_price_source: "median_pp",
      discount_pct: 75,
      potential_profit_pp: 12000,
      score: 88.5,
      deal_score: 88.5,
      sample_size: 12,
      confidence: "high",
      resolved: true,
    },
    {
      listing_id: 11,
      timestamp: "2026-06-16T10:07:00",
      seller: "Aderyn",
      item: { item_id: 2, name: "Silver Chitin Hand Wraps" },
      item_id: 2,
      item_name: "Silver Chitin Hand Wraps",
      price_raw: "6k",
      listing_price_pp: 6000,
      market_price_pp: 10000,
      market_price_source: "p25_pp",
      discount_pct: 40,
      potential_profit_pp: 4000,
      score: 40,
      deal_score: 40,
      sample_size: 5,
      confidence: "medium",
      resolved: true,
    },
  ]
    .filter((deal) => deal.discount_pct >= minDiscount)
    .filter((deal) => deal.listing_price_pp >= minPricePp)
    .filter((deal) => !resolvedOnly || deal.resolved)
    .slice(0, limit)
}

function buildListings(url: URL) {
  const q = (url.searchParams.get("q") ?? "").trim().toLowerCase()
  const limit = Number(url.searchParams.get("limit") ?? "25")
  const listings = [
    {
      listing_id: 30,
      timestamp: "2026-06-16T10:15:00",
      seller: "Mystery",
      item_id: null,
      item_name: "Unidentified Idol",
      price_raw: null,
      price_pp: null,
      source: "eq_log",
      confidence: "no_price",
      resolved: false,
    },
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
    {
      listing_id: 10,
      timestamp: "2026-06-16T10:00:00",
      seller: "Nebblastin",
      item_id: 1,
      item_name: "Stave of Shielding",
      price_raw: "4k",
      price_pp: 4000,
      source: "eq_log",
      confidence: "parsed",
      resolved: true,
    },
    ...Array.from({ length: 27 }, (_, index) => {
      const itemNumber = index + 1

      return {
        listing_id: 100 + itemNumber,
        timestamp: `2026-06-16T09:${String(59 - index).padStart(2, "0")}:00`,
        seller: `Trader ${itemNumber}`,
        item_id: 1000 + itemNumber,
        item_name: `Fine Steel Sword ${itemNumber}`,
        price_raw: `${itemNumber}k`,
        price_pp: itemNumber * 1000,
        source: "eq_log",
        confidence: "parsed",
        resolved: true,
      }
    }),
  ]

  return listings
    .filter((listing) => {
      if (!q) {
        return true
      }

      return (
        listing.item_name.toLowerCase().includes(q) ||
        (listing.seller ?? "").toLowerCase().includes(q)
      )
    })
    .slice(0, limit)
}
