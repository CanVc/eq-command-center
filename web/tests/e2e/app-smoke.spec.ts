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

test("toggles and persists dark mode", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "light" })

  await page.route("**/api/**", async (route) => {
    await fulfillApi(route)
  })

  await page.goto("/")

  await page.getByRole("button", { name: "Switch to dark mode" }).click()
  await expect(page.locator("html")).toHaveClass(/dark/)
  await expect(page.getByRole("button", { name: "Switch to light mode" })).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem("eq-command-center.theme"))).toBe("dark")

  await page.reload()
  await expect(page.locator("html")).toHaveClass(/dark/)

  await page.getByRole("button", { name: "Switch to light mode" }).click()
  await expect(page.locator("html")).not.toHaveClass(/dark/)
  await expect.poll(() => page.evaluate(() => localStorage.getItem("eq-command-center.theme"))).toBe("light")
})

test("renders local settings diagnostics as read-only status", async ({ page }) => {
  const settingsRequests: URL[] = []

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/settings/status") {
      settingsRequests.push(url)
    }

    await fulfillApi(route)
  })

  await page.goto("/settings")

  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Local Status" })).toBeVisible()
  await expect(page.getByText("API health", { exact: true })).toBeVisible()
  await expect(page.getByText("ok", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Database", { exact: true })).toBeVisible()
  await expect(page.getByText("C:/Dev/Projects/eq-command-center/data/eqmarket.sqlite")).toBeVisible()
  await expect(page.getByText("Server", { exact: true })).toBeVisible()
  await expect(page.getByText("frostreaver", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Default server: frostreaver")).toBeVisible()
  await expect(page.getByText("Magelo", { exact: true })).toBeVisible()
  await expect(page.getByText("not loaded", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "EverQuest Log File" })).toBeVisible()
  await expect(page.getByLabel("EverQuest log path")).toHaveValue(
    "C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt"
  )
  await expect(page.getByText("Last offset", { exact: true })).toBeVisible()
  await expect(page.getByText("2,048", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Browse" }).click()
  await expect(page.getByText("C:/EverQuest/Logs/eqlog_Browse_frostreaver.txt")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Last TLP Auctions Import" })).toBeVisible()
  await expect(page.getByText("tlp_auctions_prices").first()).toBeVisible()
  await expect(page.getByText("completed", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Items seen", { exact: true })).toBeVisible()
  await expect(page.getByText("50", { exact: true })).toBeVisible()
  await page.getByLabel("EverQuest log path").fill("C:/EverQuest/Logs/eqlog_New_frostreaver.txt")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Log path saved.")).toBeVisible()
  await expect(page.getByText("C:/EverQuest/Logs/eqlog_New_frostreaver.txt")).toBeVisible()
  await expect.poll(() => settingsRequests.at(-1)?.searchParams.get("server")).toBe("frostreaver")
})

test("explains when the backend log picker endpoint is unavailable", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/settings/log-path/browse") {
      await route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Not Found" }),
      })
      return
    }

    await fulfillApi(route)
  })

  await page.goto("/settings")
  await page.getByRole("button", { name: "Browse" }).click()

  await expect(page.getByText("Restart the API, then refresh this page.")).toBeVisible()
})

test("renders dashboard summary cards and trends without app item popovers", async ({ page }) => {
  const tooltipRequests: string[] = []

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (isTooltipPath(url.pathname)) {
      tooltipRequests.push(url.toString())
    }

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

  await expect(page.locator('[data-slot="hover-card-content"]')).toHaveCount(0)
  expect(tooltipRequests).toEqual([])
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
  await expect(page.locator('[data-slot="hover-card-content"]')).toHaveCount(0)

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
  await expect(page.locator('[data-slot="hover-card-content"]')).toHaveCount(0)
  expect(tooltipRequests).toEqual([])

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

test("opens item detail from item links and renders prices, history, chart, and sources", async ({ page }) => {
  const requestedPaths: string[] = []

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())
    requestedPaths.push(`${url.pathname}${url.search}`)
    await fulfillApi(route)
  })

  await page.goto("/deals")

  await page.getByRole("link", { name: "Stave of Shielding" }).click()

  await expect(page).toHaveURL(/\/items\/1$/)
  await expect(page.getByRole("heading", { name: "Item Detail", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Stave of Shielding" })).toBeVisible()
  await expect(page.getByText("Item ID 1 on frostreaver")).toBeVisible()

  await expect(page.getByText("Market median")).toBeVisible()
  await expect(page.getByText("Krono equivalent")).toBeVisible()
  await expect(page.getByText("1.00 Krono")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Stats" })).toBeVisible()
  await expect(page.getByText("HP")).toBeVisible()
  await expect(page.getByText("55", { exact: true })).toBeVisible()
  await expect(page.getByText("Ratio")).toBeVisible()
  await expect(page.getByText("0.40", { exact: true })).toBeVisible()

  await expect(page.getByRole("heading", { name: "Local Price History" })).toBeVisible()
  await expect(page.getByLabel("Local price history chart")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Local Listings" })).toBeVisible()
  await expect(page.locator("tbody")).toContainText("Stave of Shielding MQ")
  await expect(page.locator("tbody")).toContainText("42k")

  await expect(page.getByRole("link", { name: "Lucy" })).toHaveAttribute(
    "href",
    "https://lucy.allakhazam.com/item.html?id=1"
  )
  await expect(page.getByRole("link", { name: "Magelo" })).toHaveAttribute(
    "href",
    "https://eq.magelo.com/item/1"
  )
  await expect(page.getByRole("link", { name: "TLP Auctions" })).toHaveAttribute(
    "href",
    "https://www.tlp-auctions.com/search/frostreaver/Stave%20of%20Shielding"
  )

  expect(requestedPaths).toContain("/api/items/1")
  expect(requestedPaths).toContain("/api/items/1/prices?server=frostreaver")
  expect(requestedPaths).toContain("/api/items/1/listings?server=frostreaver&limit=100")
})

test("keeps item detail usable when market price is unavailable", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await fulfillApi(route)
  })

  await page.goto("/items/2")

  await expect(page.getByRole("heading", { name: "Item Detail", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Silver Chitin Hand Wraps" })).toBeVisible()
  await expect(page.getByText("No market reference")).toBeVisible()
  await expect(page.getByText("No external market price imported.")).toBeVisible()
  await expect(page.getByText("Krono equivalent")).toBeVisible()
  await expect(page.getByText("n/a").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Local Price History" })).toBeVisible()
  await expect(page.getByLabel("Local price history chart")).toBeVisible()
  await expect(page.locator("tbody")).toContainText("Silver Chitin Hand Wraps")
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

  if (url.pathname === "/api/settings/status") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildSettingsStatus(server)),
    })
    return
  }

  if (url.pathname === "/api/settings/log-path" && route.request().method() === "PUT") {
    const body = route.request().postDataJSON() as { log_path?: string | null }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildEqLogSettings(body.log_path ?? null)),
    })
    return
  }

  if (url.pathname === "/api/settings/log-path/browse" && route.request().method() === "POST") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildEqLogSettings("C:/EverQuest/Logs/eqlog_Browse_frostreaver.txt")),
    })
    return
  }

  if (url.pathname === "/api/krono/refresh" && route.request().method() === "POST") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildKronoRefresh(server)),
    })
    return
  }

  if (url.pathname === "/api/tlp-prices/refresh-jobs" && route.request().method() === "POST") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildTlpPriceRefreshJob(server, "running")),
    })
    return
  }

  const refreshJobId = tlpRefreshJobIdFromPath(url.pathname)

  if (refreshJobId !== null) {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildTlpPriceRefreshJob(server, "completed", refreshJobId)),
    })
    return
  }

  if (url.pathname === "/api/tlp-prices/refresh" && route.request().method() === "POST") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildTlpPriceRefresh(server)),
    })
    return
  }

  const refreshItemId = tlpRefreshItemIdFromPath(url.pathname)

  if (refreshItemId !== null && route.request().method() === "POST") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildTlpPriceRefresh(server, [refreshItemId])),
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

  if (url.pathname === "/api/krono/latest") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildKronoLatest(server)),
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

  const itemPricesId = itemPricesIdFromPath(url.pathname)

  if (itemPricesId !== null) {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildItemPrice(itemPricesId, server)),
    })
    return
  }

  const itemListingsId = itemListingsIdFromPath(url.pathname)

  if (itemListingsId !== null) {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildItemListings(itemListingsId)),
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

  const itemDetailId = itemDetailIdFromPath(url.pathname)

  if (itemDetailId !== null) {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildItemDetail(itemDetailId)),
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

function tlpRefreshItemIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/api\/tlp-prices\/items\/(\d+)\/refresh$/)
  return match ? Number(match[1]) : null
}

function tlpRefreshJobIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/api\/tlp-prices\/refresh-jobs\/([A-Za-z0-9_-]+)$/)
  return match ? match[1] : null
}

function itemDetailIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/api\/items\/(\d+)$/)
  return match ? Number(match[1]) : null
}

function itemPricesIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/api\/items\/(\d+)\/prices$/)
  return match ? Number(match[1]) : null
}

function itemListingsIdFromPath(pathname: string): number | null {
  const match = pathname.match(/^\/api\/items\/(\d+)\/listings$/)
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

function buildItemDetail(itemId: number) {
  return {
    item_id: itemId,
    name: tooltipItemName(itemId),
    icon_url: null,
    icon_id: itemId === 1 ? 601 : null,
    item_type: itemId === 1 ? "weapon" : "armor",
    slot: itemId === 1 ? "PRIMARY" : "HAND",
    classes: "WAR CLR PAL RNG SHD DRU MNK BRD ROG SHM NEC WIZ MAG ENC BST BER",
    races: "ALL",
    flags: "MAGIC",
    stats: {
      ac: itemId === 1 ? 12 : 8,
      hp: itemId === 1 ? 55 : 25,
      mana: itemId === 1 ? 10 : null,
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
    },
    combat: {
      damage: itemId === 1 ? 12 : null,
      delay: itemId === 1 ? 30 : null,
      ratio: itemId === 1 ? 0.4 : null,
      haste: null,
    },
    levels: {
      required_level: null,
      recommended_level: itemId === 1 ? 50 : null,
    },
    effects:
      itemId === 1
        ? [
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
          ]
        : [],
    source_primary: "fixture",
    last_imported_at: "2026-06-16T09:00:00",
  }
}

function buildItemPrice(itemId: number, server: string) {
  if (itemId === 2) {
    return {
      item_id: itemId,
      server,
      market_price_pp: null,
      market_price_source: null,
      median_pp: null,
      p25_pp: null,
      p75_pp: null,
      avg_pp: null,
      min_pp: null,
      max_pp: null,
      sample_size: null,
      confidence: null,
      last_refresh_at: null,
      source: null,
    }
  }

  return {
    item_id: itemId,
    server,
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
}

function buildItemListings(itemId: number) {
  if (itemId === 2) {
    return [
      {
        listing_id: 20,
        timestamp: "2026-06-16T10:05:00",
        seller: "Aderyn",
        item: { item_id: 2, name: "Silver Chitin Hand Wraps" },
        item_id: 2,
        item_name: "Silver Chitin Hand Wraps",
        listed_item_name: "Silver Chitin Hand Wraps",
        price_raw: "8k",
        price_pp: 8000,
        source: "eq_log",
        confidence: "parsed",
        resolved: true,
      },
    ]
  }

  return [
    {
      listing_id: 30,
      timestamp: "2026-06-16T12:00:00",
      seller: "LatestSeller",
      item: { item_id: 1, name: "Stave of Shielding" },
      item_id: 1,
      item_name: "Stave of Shielding",
      listed_item_name: "Stave of Shielding MQ",
      price_raw: "42k",
      price_pp: 42000,
      source: "eq_log",
      confidence: "parsed",
      resolved: true,
    },
    {
      listing_id: 10,
      timestamp: "2026-06-16T10:00:00",
      seller: "Nebblastin",
      item: { item_id: 1, name: "Stave of Shielding" },
      item_id: 1,
      item_name: "Stave of Shielding",
      listed_item_name: "Stave of Shielding",
      price_raw: "4k",
      price_pp: 4000,
      source: "eq_log",
      confidence: "parsed",
      resolved: true,
    },
    {
      listing_id: 9,
      timestamp: "2026-06-16T09:00:00",
      seller: "NoPrice",
      item: { item_id: 1, name: "Stave of Shielding" },
      item_id: 1,
      item_name: "Stave of Shielding",
      listed_item_name: "Stave of Shielding",
      price_raw: null,
      price_pp: null,
      source: "eq_log",
      confidence: "no_price",
      resolved: true,
    },
  ]
}

function buildKronoLatest(server: string) {
  return {
    server,
    price_pp: 16000,
    source: "fixture",
    confidence: "high",
    last_refresh_at: "2026-06-16T10:00:00",
  }
}

function buildKronoRefresh(server: string) {
  return {
    server,
    krono_updated: true,
    krono_price_pp: 16000,
    krono_listings_converted: 1,
  }
}

function buildTlpPriceRefreshJob(
  server: string,
  status: "running" | "completed",
  jobId = "fixture-job"
) {
  const completed = status === "completed" ? 1 : 0

  return {
    job_id: jobId,
    server,
    status,
    phase: status === "completed" ? "completed" : "history",
    completed,
    total: 1,
    current_item_id: status === "completed" ? null : 1,
    target_item_ids: [1],
    target_count: 1,
    limit: 500,
    max_age_hours: 6,
    history_days: 3,
    stats: status === "completed" ? buildTlpPriceRefresh(server) : null,
    error: null,
    created_at: "2026-06-16T10:00:00Z",
    started_at: "2026-06-16T10:00:00Z",
    finished_at: status === "completed" ? "2026-06-16T10:03:00Z" : null,
  }
}

function buildTlpPriceRefresh(server: string, targetItemIds: number[] = [1]) {
  return {
    server,
    target_item_ids: targetItemIds,
    target_count: targetItemIds.length,
    limit: targetItemIds.length || 500,
    max_age_hours: 6,
    history_days: 3,
    catalog_items_seen: 1,
    items_upserted: 0,
    listings_linked: 0,
    catalog_prices_upserted: 0,
    history_items_checked: targetItemIds.length,
    history_prices_upserted: targetItemIds.length,
    no_price_data: 0,
    price_refresh_failed: 0,
    krono_updated: true,
    krono_price_pp: 16000,
    krono_listings_converted: 1,
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

function buildSettingsStatus(server: string) {
  return {
    status: "ok",
    db_path: "C:/Dev/Projects/eq-command-center/data/eqmarket.sqlite",
    default_server: "frostreaver",
    active_server: server,
    latest_tlp_import: {
      import_run_id: 10,
      source_name: "tlp_auctions_prices",
      source_url: `server=${server};mode=history;history_days=3`,
      status: "completed",
      items_seen: 50,
      items_inserted: 2,
      items_updated: 12,
      error: null,
      started_at: "2026-06-16T09:59:00",
      finished_at: "2026-06-16T10:00:00",
    },
    import_runs_error: null,
    ...buildEqLogSettings("C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt"),
  }
}

function buildEqLogSettings(logPath: string | null) {
  return {
    eq_log_path: logPath,
    eq_log_exists: logPath ? true : null,
    eq_log_import_state: logPath
      ? {
          log_path: logPath,
          server: "frostreaver",
          file_size: 123456,
          file_mtime: 1780000000,
          last_position: 2048,
          updated_at: "2026-06-16T10:00:00",
        }
      : null,
    log_settings_error: null,
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
