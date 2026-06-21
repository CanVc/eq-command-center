import { expect, test, type Route } from "@playwright/test"

type DecisionStatus = "keep" | "sell" | "ignore"
type DecisionScope = "global" | "character"
type SellCategory = "sellable" | "keep" | "ignored" | "no_drop" | "unpriced" | "excluded"

type Decision = {
  scope: DecisionScope
  characterName: string | null
  status: DecisionStatus
  notes: string | null
}

type SellFixtureItem = {
  characterName: string
  itemId: number
  itemName: string
  quantity: number
  areas: Array<"carried" | "bank" | "shared_bank">
  areaQuantities: Partial<Record<"carried" | "bank" | "shared_bank", number>>
  unitPrice: number | null
  source: string | null
  sourceDetail: string | null
  confidence: string | null
  baseCategory: SellCategory
  isNoDrop?: boolean
  defaultExclusionReasons?: string[]
  itemType?: string | null
  flags?: string | null
}

test.beforeEach(async ({ page }) => {
  resetSellFixtureState()

  await page.route("https://www.magelocdn.com/**", async (route) => {
    await route.abort()
  })
})

test("sorts and filters sell inventory candidates", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await fulfillSellInventoryApi(route)
  })

  await page.goto("/characters")
  await page.getByRole("tab", { name: "Sell" }).click()

  await expect(page.getByRole("heading", { name: "Sell Inventory" })).toBeVisible()
  await expect(page.getByText("11,500pp")).toBeVisible()

  const rows = page.locator("tbody tr")
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText("Velium Gem")
  await expect(rows.nth(1)).toContainText("Silk Swatch")
  await expect(page.locator("tbody")).not.toContainText("No Price Relic")

  await page.getByRole("button", { name: /^Item/ }).click()
  await expect(rows.nth(0)).toContainText("Silk Swatch")
  await expect(rows.nth(1)).toContainText("Velium Gem")

  await page.getByLabel("Sell zone filter").selectOption("bank")
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText("Velium Gem")

  await page.getByLabel("Sell zone filter").selectOption("all")
  await page.getByLabel("Sell status filter").selectOption("all")
  await page.getByLabel("Sell price filter").selectOption("unpriced")
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText("No Price Relic")

  await page.getByLabel("Sell price filter").selectOption("all")
  await page.getByLabel("Sell status filter").selectOption("no_drop")
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText("No Drop Blade")

  await page.getByLabel("Sell status filter").selectOption("sellable")
  await page.getByLabel("Sell character filter").selectOption("Beta")
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText("Silk Swatch")
  await expect(rows.first()).not.toContainText("Velium Gem")
})

test("updates a global sell decision and keeps it after reload", async ({ page }) => {
  const decisionRequests: string[] = []

  await page.route("**/api/**", async (route) => {
    await fulfillSellInventoryApi(route, { decisionRequests })
  })

  await page.goto("/characters")
  await page.getByRole("tab", { name: "Sell" }).click()

  const row = page.getByRole("row", { name: /Silk Swatch/ })
  await row.getByLabel("Decision note for Silk Swatch on Beta").fill("Sell in EC")
  await row.getByRole("button", { name: "Sell" }).click()

  await expect.poll(() => decisionRequests.at(-1)).toContain("/api/inventory/items/202/decision")
  await expect(row).toContainText("Sell global")
  await expect(row).toContainText("Sell in EC")

  await page.reload()
  await page.getByRole("tab", { name: "Sell" }).click()

  const reloadedRow = page.getByRole("row", { name: /Silk Swatch/ })
  await expect(reloadedRow).toContainText("Sell global")
  await expect(reloadedRow).toContainText("Sell in EC")
})

async function fulfillSellInventoryApi(
  route: Route,
  options: { decisionRequests?: string[] } = {}
) {
  const url = new URL(route.request().url())
  const server = url.searchParams.get("server") ?? "frostreaver"

  if (url.pathname === "/api/runtime/status") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        server,
        max_age_hours: 6,
        max_age_minutes: 360,
        stale_item_count: 0,
        latest_log_sale_at: null,
        log_watcher: null,
      }),
    })
    return
  }

  if (url.pathname === "/api/characters") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildCharacters(server)),
    })
    return
  }

  const globalDecisionMatch = url.pathname.match(/^\/api\/inventory\/items\/(\d+)\/decision$/)
  if (globalDecisionMatch) {
    const itemId = Number(globalDecisionMatch[1])
    options.decisionRequests?.push(url.pathname)

    if (route.request().method() === "DELETE") {
      globalDecisions.delete(itemId)
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(buildDecisionRecord(server, itemId, null)),
      })
      return
    }

    const payload = JSON.parse(route.request().postData() ?? "{}") as { status: DecisionStatus; notes?: string | null }
    const decision: Decision = {
      scope: "global",
      characterName: null,
      status: payload.status,
      notes: payload.notes ?? null,
    }
    globalDecisions.set(itemId, decision)
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildDecisionRecord(server, itemId, decision)),
    })
    return
  }

  const characterDecisionMatch = url.pathname.match(/^\/api\/characters\/([^/]+)\/inventory\/items\/(\d+)\/decision$/)
  if (characterDecisionMatch) {
    const characterName = decodeURIComponent(characterDecisionMatch[1])
    const itemId = Number(characterDecisionMatch[2])
    const key = `${characterName}:${itemId}`
    options.decisionRequests?.push(url.pathname)

    if (route.request().method() === "DELETE") {
      characterDecisions.delete(key)
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(buildDecisionRecord(server, itemId, null, characterName)),
      })
      return
    }

    const payload = JSON.parse(route.request().postData() ?? "{}") as { status: DecisionStatus; notes?: string | null }
    const decision: Decision = {
      scope: "character",
      characterName,
      status: payload.status,
      notes: payload.notes ?? null,
    }
    characterDecisions.set(key, decision)
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildDecisionRecord(server, itemId, decision, characterName)),
    })
    return
  }

  if (url.pathname === "/api/inventory/sell-candidates") {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildSellCandidatesPayload(server)),
    })
    return
  }

  const characterSellMatch = url.pathname.match(/^\/api\/characters\/([^/]+)\/sell-candidates$/)
  if (characterSellMatch) {
    const characterName = decodeURIComponent(characterSellMatch[1])
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildSellCandidatesPayload(server, characterName)),
    })
    return
  }

  const equipmentMatch = url.pathname.match(/^\/api\/characters\/([^/]+)\/equipment$/)
  if (equipmentMatch) {
    const characterName = decodeURIComponent(equipmentMatch[1])
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        character_name: characterName,
        server,
        last_import: null,
        slot_order: [],
        slots: {},
      }),
    })
    return
  }

  const inventoryMatch = url.pathname.match(/^\/api\/characters\/([^/]+)\/inventory$/)
  if (inventoryMatch) {
    const characterName = decodeURIComponent(inventoryMatch[1])
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        character_name: characterName,
        server,
        area: url.searchParams.get("area") ?? "all",
        available_areas: ["carried", "bank", "shared_bank"],
        include_locations: false,
        last_import: null,
        item_count: 0,
        location_count: 0,
        total_quantity: 0,
        items: [],
      }),
    })
    return
  }

  await route.fulfill({
    status: 404,
    contentType: "text/plain",
    body: `unknown fixture endpoint ${url.pathname}`,
  })
}

const fixtureItems: SellFixtureItem[] = [
  {
    characterName: "Alpha",
    itemId: 201,
    itemName: "Velium Gem",
    quantity: 2,
    areas: ["bank"],
    areaQuantities: { bank: 2 },
    unitPrice: 5000,
    source: "market_prices",
    sourceDetail: "median_pp",
    confidence: "high",
    baseCategory: "sellable",
    itemType: "misc",
    flags: "MAGIC",
  },
  {
    characterName: "Beta",
    itemId: 202,
    itemName: "Silk Swatch",
    quantity: 3,
    areas: ["carried"],
    areaQuantities: { carried: 3 },
    unitPrice: 500,
    source: "recent_local_listings",
    sourceDetail: "avg_price_pp",
    confidence: "medium",
    baseCategory: "sellable",
    itemType: "misc",
    flags: "MAGIC",
  },
  {
    characterName: "Alpha",
    itemId: 203,
    itemName: "No Price Relic",
    quantity: 1,
    areas: ["carried"],
    areaQuantities: { carried: 1 },
    unitPrice: null,
    source: null,
    sourceDetail: null,
    confidence: null,
    baseCategory: "unpriced",
    itemType: "misc",
    flags: "MAGIC",
  },
  {
    characterName: "Alpha",
    itemId: 204,
    itemName: "No Drop Blade",
    quantity: 1,
    areas: ["bank"],
    areaQuantities: { bank: 1 },
    unitPrice: 8000,
    source: "market_prices",
    sourceDetail: "median_pp",
    confidence: "low",
    baseCategory: "no_drop",
    isNoDrop: true,
    itemType: "weapon",
    flags: "MAGIC,NO_DROP",
  },
  {
    characterName: "Beta",
    itemId: 205,
    itemName: "Light Backpack",
    quantity: 1,
    areas: ["carried"],
    areaQuantities: { carried: 1 },
    unitPrice: 50,
    source: "market_prices",
    sourceDetail: "median_pp",
    confidence: "low",
    baseCategory: "excluded",
    defaultExclusionReasons: ["container"],
    itemType: "container",
    flags: null,
  },
  {
    characterName: "Alpha",
    itemId: 206,
    itemName: "Keep Idol",
    quantity: 1,
    areas: ["shared_bank"],
    areaQuantities: { shared_bank: 1 },
    unitPrice: 2000,
    source: "manual_override",
    sourceDetail: "manual_override_pp",
    confidence: "manual",
    baseCategory: "sellable",
    itemType: "misc",
    flags: "MAGIC",
  },
]

const globalDecisions = new Map<number, Decision>()
const characterDecisions = new Map<string, Decision>()

function resetSellFixtureState() {
  globalDecisions.clear()
  characterDecisions.clear()
  characterDecisions.set("Alpha:206", {
    scope: "character",
    characterName: "Alpha",
    status: "keep",
    notes: "Hold for alt",
  })
}

function buildCharacters(server: string) {
  return [
    buildCharacter("Alpha", server),
    buildCharacter("Beta", server),
  ]
}

function buildCharacter(characterName: string, server: string) {
  return {
    character_name: characterName,
    name: characterName,
    server,
    character_class: "Rogue",
    level: 60,
    notes: null,
    created_at: "2026-06-16T09:00:00",
    updated_at: "2026-06-16T10:00:00",
    last_imported_at: "2026-06-16T10:00:00",
    last_import: null,
    freshness: { imported: true, last_imported_at: "2026-06-16T10:00:00", age_seconds: 300 },
    equipment_item_count: 0,
    inventory_item_count: 3,
    inventory_quantity: 4,
    starter_item_count: 0,
    distinct_item_count: 3,
    unenriched_item_count: 0,
    unpriced_item_count: 1,
  }
}

function buildSellCandidatesPayload(server: string, characterName: string | null = null) {
  const items = fixtureItems
    .filter((item) => characterName === null || item.characterName === characterName)
    .map((item) => buildSellCandidate(item, server))
    .sort(compareCandidatePayloads)
  const categories = {
    sellable: items.filter((item) => item.category === "sellable"),
    keep: items.filter((item) => item.category === "keep"),
    ignored: items.filter((item) => item.category === "ignored"),
    no_drop: items.filter((item) => item.category === "no_drop"),
    unpriced: items.filter((item) => item.category === "unpriced"),
    excluded: items.filter((item) => item.category === "excluded"),
  }

  return {
    scope: characterName === null ? "global" : "character",
    character_name: characterName,
    server,
    local_listing_max_age_days: 30,
    item_count: items.length,
    total_quantity: items.reduce((total, item) => total + item.quantity, 0),
    sellable_total_value_pp: categories.sellable.reduce((total, item) => total + (item.estimated_total_pp ?? 0), 0),
    categories,
    items,
    global_items: [],
  }
}

function buildSellCandidate(item: SellFixtureItem, server: string) {
  const characterDecision = characterDecisions.get(`${item.characterName}:${item.itemId}`)
  const globalDecision = globalDecisions.get(item.itemId)
  const decision = characterDecision ?? globalDecision ?? null
  const estimatedTotal = item.unitPrice === null ? null : item.unitPrice * item.quantity
  const category = categoryForItem(item, decision)

  return {
    character_name: item.characterName,
    server,
    item_id: item.itemId,
    item_name: item.itemName,
    name: item.itemName,
    normalized_item_name: item.itemName.toLowerCase(),
    quantity: item.quantity,
    areas: item.areas,
    area_quantities: item.areaQuantities,
    location_count: item.areas.length,
    raw_item_names: [item.itemName],
    item_type: item.itemType ?? null,
    flags: item.flags ?? null,
    source_primary: "fixture",
    icon_id: item.itemId,
    last_imported_at: "2026-06-16T10:00:00",
    is_starter_item: false,
    is_no_trade_import: false,
    is_no_drop: Boolean(item.isNoDrop),
    is_container: item.defaultExclusionReasons?.includes("container") ?? false,
    is_consumable: false,
    is_augment: false,
    default_exclusion_reasons: item.defaultExclusionReasons ?? [],
    decision_status: decision?.status ?? null,
    decision: decision ? buildDecisionPayload(decision) : null,
    estimated_unit_price_pp: item.unitPrice,
    estimated_total_pp: estimatedTotal,
    price_source: item.source,
    price_source_detail: item.sourceDetail,
    confidence: item.confidence,
    price_sample_size: item.unitPrice === null ? null : 3,
    price_last_seen_at: item.unitPrice === null ? null : "2026-06-16T10:00:00",
    category,
  }
}

function categoryForItem(item: SellFixtureItem, decision: Decision | null): SellCategory {
  if (decision?.status === "keep") {
    return "keep"
  }
  if (decision?.status === "ignore") {
    return "ignored"
  }
  if (decision?.status === "sell") {
    return item.unitPrice === null ? "unpriced" : "sellable"
  }
  return item.baseCategory
}

function buildDecisionPayload(decision: Decision) {
  return {
    decision_id: decision.status === "keep" ? 206 : 202,
    scope: decision.scope,
    status: decision.status,
    notes: decision.notes,
    created_at: "2026-06-16T10:00:00",
    updated_at: "2026-06-16T10:00:00",
  }
}

function buildDecisionRecord(
  server: string,
  itemId: number,
  decision: Decision | null,
  characterName: string | null = null
) {
  const item = fixtureItems.find((candidate) => candidate.itemId === itemId)

  return {
    decision_id: decision ? itemId : null,
    server,
    scope: decision?.scope ?? (characterName ? "character" : "global"),
    scope_key: decision?.scope === "character" ? decision.characterName?.toLowerCase() : "*",
    character_name: decision?.characterName ?? characterName,
    item_id: itemId,
    item_name: item?.itemName ?? "Unknown Item",
    normalized_item_name: item?.itemName.toLowerCase() ?? "unknown item",
    status: decision?.status ?? null,
    notes: decision?.notes ?? null,
    created_at: decision ? "2026-06-16T10:00:00" : null,
    updated_at: decision ? "2026-06-16T10:00:00" : null,
  }
}

function compareCandidatePayloads(a: { estimated_total_pp: number | null; character_name: string; item_name: string }, b: { estimated_total_pp: number | null; character_name: string; item_name: string }) {
  const aValue = a.estimated_total_pp ?? -1
  const bValue = b.estimated_total_pp ?? -1
  if (aValue !== bValue) {
    return bValue - aValue
  }

  const characterCompare = a.character_name.localeCompare(b.character_name)
  return characterCompare === 0 ? a.item_name.localeCompare(b.item_name) : characterCompare
}
