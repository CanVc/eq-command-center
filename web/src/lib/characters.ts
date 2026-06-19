import type {
  CharacterEquipmentResponse,
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

const AREA_LABELS: Record<CharacterInventoryArea, string> = {
  all: "All",
  carried: "Carried",
  bank: "Bank",
  shared_bank: "Shared Bank",
}

export function characterClassLevelLabel(character: Pick<CharacterSummary, "character_class" | "level">): string {
  const classLabel = character.character_class?.trim() || "Class unknown"
  const levelLabel = character.level === null || character.level === undefined ? "Level unknown" : `Level ${character.level}`
  return `${classLabel} · ${levelLabel}`
}

export function inventoryAreaLabel(area: CharacterInventoryArea): string {
  return AREA_LABELS[area]
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
