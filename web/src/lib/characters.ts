import type {
  CharacterEquipmentResponse,
  CharacterUpgradeProfile,
  CharacterUpgradeSource,
  CharacterUpgradeSourceFilter,
  CharacterInventoryArea,
  CharacterInventoryGroup,
  CharacterInventoryItemDetail,
  CharacterSummary,
} from "@/lib/api"

export const CHARACTER_INVENTORY_AREAS: CharacterInventoryArea[] = [
  "all",
  "carried",
  "bank",
  "shared_bank",
]

export const CHARACTER_UPGRADE_SLOTS = [
  "all",
  "CHARM",
  "EAR",
  "HEAD",
  "FACE",
  "NECK",
  "SHOULDERS",
  "ARMS",
  "BACK",
  "WRIST",
  "RANGE",
  "HANDS",
  "PRIMARY",
  "SECONDARY",
  "FINGER",
  "CHEST",
  "LEGS",
  "FEET",
  "WAIST",
  "POWER_SOURCE",
  "AMMO",
] as const

const AREA_LABELS: Record<CharacterInventoryArea, string> = {
  all: "All",
  carried: "Carried",
  bank: "Bank",
  shared_bank: "Shared Bank",
}

const UPGRADE_SLOT_LABELS: Record<(typeof CHARACTER_UPGRADE_SLOTS)[number], string> = {
  all: "All slots",
  CHARM: "Charm",
  EAR: "Ear",
  HEAD: "Head",
  FACE: "Face",
  NECK: "Neck",
  SHOULDERS: "Shoulders",
  ARMS: "Arms",
  BACK: "Back",
  WRIST: "Wrist",
  RANGE: "Range",
  HANDS: "Hands",
  PRIMARY: "Primary",
  SECONDARY: "Secondary",
  FINGER: "Finger",
  CHEST: "Chest",
  LEGS: "Legs",
  FEET: "Feet",
  WAIST: "Waist",
  POWER_SOURCE: "Power Source",
  AMMO: "Ammo",
}

export function characterClassLevelLabel(character: Pick<CharacterSummary, "character_class" | "level">): string {
  const classLabel = character.character_class?.trim() || "Class unknown"
  const levelLabel = character.level === null || character.level === undefined ? "Level unknown" : `Level ${character.level}`
  return `${classLabel} · ${levelLabel}`
}

export function inventoryAreaLabel(area: CharacterInventoryArea): string {
  return AREA_LABELS[area]
}

export function upgradeSlotLabel(slot: string): string {
  return UPGRADE_SLOT_LABELS[slot as (typeof CHARACTER_UPGRADE_SLOTS)[number]] ?? slot.replaceAll("_", " ")
}

export function upgradeSourceFilterLabel(source: CharacterUpgradeSourceFilter): string {
  switch (source) {
    case "all":
      return "Owned + Market"
    case "owned":
      return "Owned"
    case "market":
      return "Market"
  }
}

export function upgradeSourceLabel(source: CharacterUpgradeSource): string {
  switch (source) {
    case "owned":
      return "Owned"
    case "local_listing":
      return "Local listing"
    case "market_price":
      return "Market price"
  }
}

export function upgradeProfileLabel(profile: CharacterUpgradeProfile): string {
  switch (profile) {
    case "auto":
      return "Auto"
    case "tank":
      return "Tank"
    case "monk":
      return "Monk"
    case "sk":
      return "SK"
  }
}

export function isStarterOrNoTradeImport(
  item: Pick<CharacterInventoryItemDetail, "is_starter_item" | "is_no_trade_import">
): boolean {
  return Boolean(item.is_starter_item || item.is_no_trade_import)
}

export function equippedItemCount(equipment: CharacterEquipmentResponse | null): number {
  if (equipment === null) {
    return 0
  }

  return Object.values(equipment.slots).filter((slot) => slot.item !== null).length
}

export function areaQuantityLabel(item: Pick<CharacterInventoryGroup, "areas" | "area_quantities">): string {
  return item.areas
    .map((area) => {
      const quantity = item.area_quantities[area]
      return quantity ? `${inventoryAreaLabel(area)} ${quantity}` : inventoryAreaLabel(area)
    })
    .join(" · ")
}
