import { expect, test, type Route } from "@playwright/test"

test.beforeEach(async ({ page }) => {
  await page.route("https://www.magelocdn.com/**", async (route) => {
    await route.abort()
  })
})

test("renders the Characters paperdoll and grouped inventory", async ({ page }) => {
  const inventoryRequests: URL[] = []

  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname.endsWith("/inventory")) {
      inventoryRequests.push(url)
    }

    await fulfillCharactersApi(route)
  })

  await page.goto("/characters")

  await expect(page.locator("h1")).toHaveText("Characters")
  await expect(page.getByRole("heading", { name: "Character Inventory" })).toBeVisible()
  await expect(page.getByRole("button", { name: /Dreadbank/ })).toHaveAttribute("aria-pressed", "true")

  await expect(page.getByRole("heading", { name: "Equipment Paperdoll" })).toBeVisible()
  await expect(page.getByLabel("Ear 1 slot")).toContainText("Earring of Essence")
  await expect(page.getByLabel("Ear 2 slot")).toContainText("Apprentice Earring *")
  await expect(page.getByLabel("Wrist 1 slot")).toContainText("Bracelet of Woven Grass")
  await expect(page.getByLabel("Wrist 2 slot")).toContainText("Runed Mithril Bracer")
  await expect(page.getByLabel("Finger 1 slot")).toContainText("Platinum Fire Wedding Ring")
  await expect(page.getByLabel("Finger 2 slot")).toContainText("Electrum Star Ruby Ring")
  await expect(page.getByRole("link", { name: "Stave of Shielding" })).toHaveAttribute("rel", "eq:item:1")
  await expect(page.getByText("Starter / No Trade *").first()).toBeVisible()
  await expect(page.getByText("No price").first()).toBeVisible()

  await expect(page.getByRole("heading", { name: "Inventory List" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "All" })).toBeVisible()
  await expect(page.locator("tbody")).toContainText("Bone Chips")
  await expect(page.locator("tbody")).toContainText("Backpack")
  await expect(page.locator("tbody")).toContainText("Shared Platinum Satchel")

  await page.getByRole("tab", { name: "Bank", exact: true }).click()
  await expect.poll(() => inventoryRequests.at(-1)?.searchParams.get("area")).toBe("bank")
  await expect(page.locator("tbody")).toContainText("Journeyman's Boots")
  await expect(page.locator("tbody")).not.toContainText("Bone Chips")

  await page.getByRole("tab", { name: "Shared Bank" }).click()
  await expect.poll(() => inventoryRequests.at(-1)?.searchParams.get("area")).toBe("shared_bank")
  await expect(page.locator("tbody")).toContainText("Shared Platinum Satchel")
})

test("supports selecting a character without an inventory import", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    await fulfillCharactersApi(route)
  })

  await page.goto("/characters")
  await page.getByRole("button", { name: /Lucy/ }).click()

  await expect(page.getByRole("button", { name: /Lucy/ })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByText("No import found for this character.")).toBeVisible()
  await expect(page.getByText("No equipment imported for Lucy.")).toBeVisible()
  await expect(page.getByText("No inventory items imported for Lucy.")).toBeVisible()
})

test("shows the shared page error state when the characters API fails", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url())

    if (url.pathname === "/api/characters") {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "characters database unavailable" }),
      })
      return
    }

    await fulfillCharactersApi(route)
  })

  await page.goto("/characters")

  await expect(page.getByText("Unable to load Characters")).toBeVisible()
  await expect(page.getByText("characters database unavailable")).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible()
})

async function fulfillCharactersApi(route: Route) {
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

  const equipmentCharacter = characterNameFromPath(url.pathname, "equipment")

  if (equipmentCharacter) {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildEquipment(decodeURIComponent(equipmentCharacter), server)),
    })
    return
  }

  const inventoryCharacter = characterNameFromPath(url.pathname, "inventory")

  if (inventoryCharacter) {
    const area = url.searchParams.get("area") ?? "all"
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(buildInventory(decodeURIComponent(inventoryCharacter), server, area)),
    })
    return
  }

  await route.fulfill({
    status: 404,
    contentType: "text/plain",
    body: "unknown fixture endpoint",
  })
}

function characterNameFromPath(pathname: string, endpoint: "equipment" | "inventory"): string | null {
  const match = pathname.match(new RegExp(`^/api/characters/([^/]+)/${endpoint}$`))
  return match ? match[1] : null
}

function buildCharacters(server: string) {
  return [
    {
      character_name: "Dreadbank",
      name: "Dreadbank",
      server,
      character_class: "Shadow Knight",
      level: 60,
      notes: null,
      created_at: "2026-06-16T09:00:00",
      updated_at: "2026-06-16T10:00:00",
      last_imported_at: "2026-06-16T10:00:00",
      last_import: buildImport("Dreadbank", server),
      freshness: { imported: true, last_imported_at: "2026-06-16T10:00:00", age_seconds: 300 },
      equipment_item_count: 8,
      inventory_item_count: 5,
      inventory_quantity: 15,
      starter_item_count: 1,
      distinct_item_count: 12,
      unenriched_item_count: 1,
      unpriced_item_count: 3,
    },
    {
      character_name: "Lucy",
      name: "Lucy",
      server,
      character_class: null,
      level: null,
      notes: null,
      created_at: "2026-06-16T09:00:00",
      updated_at: "2026-06-16T09:00:00",
      last_imported_at: null,
      last_import: null,
      freshness: { imported: false, last_imported_at: null, age_seconds: null },
      equipment_item_count: 0,
      inventory_item_count: 0,
      inventory_quantity: 0,
      starter_item_count: 0,
      distinct_item_count: 0,
      unenriched_item_count: 0,
      unpriced_item_count: 0,
    },
  ]
}

function buildImport(characterName: string, server: string) {
  return {
    inventory_import_id: 1,
    character_name: characterName,
    server,
    source_file: `C:/EverQuest/${characterName}-Inventory.txt`,
    source_hash: "fixture",
    source_size_bytes: 1234,
    parser_version: "fixture",
    rows_seen: 20,
    rows_imported: 18,
    equipment_items_imported: 8,
    inventory_items_imported: 10,
    starter_items_seen: 1,
    empty_rows_skipped: 2,
    status: "completed",
    error: null,
    imported_at: "2026-06-16T10:00:00",
    age_seconds: 300,
  }
}

function buildEquipment(characterName: string, server: string) {
  const slots = Object.fromEntries(
    SLOT_DEFINITIONS.map(([slotKey, slot, slotIndex, label]) => [
      slotKey,
      { slot_key: slotKey, slot, slot_index: slotIndex, label, item: null },
    ])
  )

  if (characterName === "Dreadbank") {
    slots.EAR_1.item = buildItem({ itemId: 101, name: "Earring of Essence", slot: "EAR", iconId: 501 })
    slots.EAR_2.item = buildItem({
      itemId: 102,
      name: "Apprentice Earring",
      slot: "EAR",
      starter: true,
      noTradeImport: true,
      enriched: false,
      hasPrice: false,
    })
    slots.WRIST_1.item = buildItem({ itemId: 103, name: "Bracelet of Woven Grass", slot: "WRIST", marketPrice: 2000 })
    slots.WRIST_2.item = buildItem({ itemId: 104, name: "Runed Mithril Bracer", slot: "WRIST", marketPrice: 7500 })
    slots.FINGER_1.item = buildItem({ itemId: 105, name: "Platinum Fire Wedding Ring", slot: "FINGER", marketPrice: 3000 })
    slots.FINGER_2.item = buildItem({ itemId: 106, name: "Electrum Star Ruby Ring", slot: "FINGER", marketPrice: 500 })
    slots.PRIMARY.item = buildItem({ itemId: 1, name: "Stave of Shielding", slot: "PRIMARY", iconId: 601, marketPrice: 16000 })
    slots.CHEST.item = buildItem({ itemId: 107, name: "Cobalt Breastplate", slot: "CHEST", iconId: 701, marketPrice: 45000 })
  }

  return {
    character_name: characterName,
    server,
    last_import: characterName === "Dreadbank" ? buildImport(characterName, server) : null,
    slot_order: SLOT_DEFINITIONS.map(([slotKey]) => slotKey),
    slots,
  }
}

function buildInventory(characterName: string, server: string, area: string) {
  const allItems = characterName === "Dreadbank" ? buildInventoryItems() : []
  const items = area === "all" ? allItems : allItems.filter((item) => item.areas.includes(area))

  return {
    character_name: characterName,
    server,
    area,
    available_areas: ["carried", "bank", "shared_bank"],
    include_locations: false,
    last_import: characterName === "Dreadbank" ? buildImport(characterName, server) : null,
    item_count: items.length,
    location_count: items.length,
    total_quantity: items.reduce((total, item) => total + item.quantity, 0),
    items,
  }
}

function buildInventoryItems() {
  return [
    buildInventoryGroup({
      itemId: 201,
      name: "Bone Chips",
      quantity: 10,
      areas: ["carried"],
      areaQuantities: { carried: 10 },
      marketPrice: null,
      hasPrice: false,
    }),
    buildInventoryGroup({
      itemId: 202,
      name: "Backpack",
      quantity: 1,
      areas: ["carried"],
      areaQuantities: { carried: 1 },
      container: true,
      marketPrice: 50,
    }),
    buildInventoryGroup({
      itemId: 203,
      name: "Journeyman's Boots",
      quantity: 1,
      areas: ["bank"],
      areaQuantities: { bank: 1 },
      marketPrice: 8000,
    }),
    buildInventoryGroup({
      itemId: 204,
      name: "Shared Platinum Satchel",
      quantity: 1,
      areas: ["shared_bank"],
      areaQuantities: { shared_bank: 1 },
      marketPrice: 1200,
    }),
  ]
}

function buildInventoryGroup({
  itemId,
  name,
  quantity,
  areas,
  areaQuantities,
  container = false,
  marketPrice = 1000,
  hasPrice = true,
}: {
  itemId: number
  name: string
  quantity: number
  areas: string[]
  areaQuantities: Record<string, number>
  container?: boolean
  marketPrice?: number | null
  hasPrice?: boolean
}) {
  const item = buildItem({ itemId, name, slot: container ? "BAG" : "ANY", marketPrice, hasPrice })

  return {
    item_id: itemId,
    item_name: name,
    name,
    quantity,
    areas,
    area_quantities: areaQuantities,
    raw_item_names: [name],
    is_starter_item: false,
    is_no_trade_import: false,
    is_container: container,
    is_augment: false,
    has_price: hasPrice,
    enriched: true,
    enrichment_status: "enriched",
    locations: null,
    item: { ...item, is_container: container, quantity },
  }
}

function buildItem({
  itemId,
  name,
  slot,
  iconId = null,
  starter = false,
  noTradeImport = false,
  enriched = true,
  marketPrice = 1000,
  hasPrice = true,
}: {
  itemId: number
  name: string
  slot: string
  iconId?: number | null
  starter?: boolean
  noTradeImport?: boolean
  enriched?: boolean
  marketPrice?: number | null
  hasPrice?: boolean
}) {
  return {
    item_id: itemId,
    name,
    raw_item_name: name,
    imported_name: name,
    normalized_name: name.toLowerCase(),
    icon_url: null,
    icon_id: iconId,
    item_type: slot === "BAG" ? "container" : "gear",
    slot,
    slot_mask: null,
    slot_labels: [slot],
    slot_display: slot,
    classes: null,
    races: null,
    flags: noTradeImport ? "NO_TRADE_IMPORT" : "MAGIC",
    quantity: 1,
    raw_location: null,
    stats: { ac: 5, hp: 25, mana: 10 },
    combat: { damage: null, delay: null, ratio: null, haste: null },
    levels: { required_level: null, recommended_level: null },
    source_primary: enriched ? "fixture" : "inventory_dump",
    last_imported_at: enriched ? "2026-06-16T10:00:00" : null,
    enriched,
    enrichment_status: enriched ? "enriched" : "inventory_stub",
    is_starter_item: starter,
    is_no_trade_import: noTradeImport,
    is_container: slot === "BAG",
    is_augment: false,
    augment_parent_location: null,
    has_price: hasPrice,
    price: {
      market_price_pp: marketPrice,
      market_price_source: marketPrice ? "median_pp" : null,
      median_pp: marketPrice,
      p25_pp: marketPrice,
      p75_pp: marketPrice,
      avg_pp: marketPrice,
      min_pp: marketPrice,
      max_pp: marketPrice,
      sample_size: marketPrice ? 3 : null,
      confidence: marketPrice ? "medium" : null,
      last_refresh_at: marketPrice ? "2026-06-16T10:00:00" : null,
      source: marketPrice ? "fixture" : null,
    },
  }
}

const SLOT_DEFINITIONS = [
  ["CHARM", "CHARM", 1, "Charm"],
  ["EAR_1", "EAR", 1, "Ear 1"],
  ["HEAD", "HEAD", 1, "Head"],
  ["FACE", "FACE", 1, "Face"],
  ["EAR_2", "EAR", 2, "Ear 2"],
  ["NECK", "NECK", 1, "Neck"],
  ["SHOULDERS", "SHOULDERS", 1, "Shoulders"],
  ["ARMS", "ARMS", 1, "Arms"],
  ["BACK", "BACK", 1, "Back"],
  ["WRIST_1", "WRIST", 1, "Wrist 1"],
  ["WRIST_2", "WRIST", 2, "Wrist 2"],
  ["RANGE", "RANGE", 1, "Range"],
  ["HANDS", "HANDS", 1, "Hands"],
  ["PRIMARY", "PRIMARY", 1, "Primary"],
  ["SECONDARY", "SECONDARY", 1, "Secondary"],
  ["FINGER_1", "FINGER", 1, "Finger 1"],
  ["FINGER_2", "FINGER", 2, "Finger 2"],
  ["CHEST", "CHEST", 1, "Chest"],
  ["LEGS", "LEGS", 1, "Legs"],
  ["FEET", "FEET", 1, "Feet"],
  ["WAIST", "WAIST", 1, "Waist"],
  ["POWER_SOURCE", "POWER_SOURCE", 1, "Power Source"],
  ["AMMO", "AMMO", 1, "Ammo"],
] as const
