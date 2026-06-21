import type {
  CharacterEquipmentResponse,
  CharacterUpgradeStat,
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

export const CHARACTER_UPGRADE_STATS: CharacterUpgradeStat[] = [
  "ac",
  "hp",
  "mana",
  "endurance",
  "sv_fire",
  "sv_cold",
  "sv_magic",
  "sv_poison",
  "sv_disease",
  "resists_total",
  "str",
  "sta",
  "agi",
  "dex",
  "wis",
  "int",
  "cha",
  "base_stats_total",
  "heroic_str",
  "heroic_sta",
  "heroic_agi",
  "heroic_dex",
  "heroic_wis",
  "heroic_int",
  "heroic_cha",
  "hp_regen",
  "mana_regen",
  "endurance_regen",
  "damage",
  "delay",
  "ratio",
  "haste",
]

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

const UPGRADE_STAT_LABELS: Record<CharacterUpgradeStat, string> = {
  ac: "AC",
  hp: "HP",
  mana: "Mana",
  endurance: "Endurance",
  hp_regen: "HP Regen",
  mana_regen: "Mana Regen",
  endurance_regen: "End Regen",
  str: "STR",
  sta: "STA",
  agi: "AGI",
  dex: "DEX",
  wis: "WIS",
  int: "INT",
  cha: "CHA",
  heroic_str: "Heroic STR",
  heroic_sta: "Heroic STA",
  heroic_agi: "Heroic AGI",
  heroic_dex: "Heroic DEX",
  heroic_wis: "Heroic WIS",
  heroic_int: "Heroic INT",
  heroic_cha: "Heroic CHA",
  sv_magic: "Magic Resist",
  sv_fire: "Fire Resist",
  sv_cold: "Cold Resist",
  sv_poison: "Poison Resist",
  sv_disease: "Disease Resist",
  resists_total: "Total Resists",
  base_stats_total: "Base Stats",
  damage: "Damage",
  delay: "Delay",
  ratio: "Ratio",
  haste: "Haste",
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

export function upgradeStatLabel(stat: CharacterUpgradeStat | string): string {
  return UPGRADE_STAT_LABELS[stat as CharacterUpgradeStat] ?? stat.replaceAll("_", " ")
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
