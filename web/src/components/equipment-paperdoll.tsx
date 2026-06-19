import type { CSSProperties } from "react"

import { ItemLink } from "@/components/item-link"
import { Badge } from "@/components/ui/badge"
import type { CharacterEquipmentItem, CharacterEquipmentResponse, CharacterEquipmentSlot } from "@/lib/api"
import { equippedItemCount, isStarterOrNoTradeImport } from "@/lib/characters"
import { formatPrice } from "@/lib/format"
import { cn } from "@/lib/utils"

type EquipmentPaperdollProps = {
  equipment: CharacterEquipmentResponse
  server: string
}

type SlotPlacement = {
  column: number
  row: number
}

const PAPERDOLL_PLACEMENTS: Record<string, SlotPlacement> = {
  CHARM: { column: 1, row: 1 },
  EAR_1: { column: 2, row: 1 },
  HEAD: { column: 3, row: 1 },
  FACE: { column: 4, row: 1 },
  EAR_2: { column: 5, row: 1 },
  NECK: { column: 3, row: 2 },
  SHOULDERS: { column: 2, row: 2 },
  ARMS: { column: 4, row: 2 },
  BACK: { column: 1, row: 3 },
  WRIST_1: { column: 2, row: 3 },
  CHEST: { column: 3, row: 3 },
  WRIST_2: { column: 4, row: 3 },
  RANGE: { column: 5, row: 3 },
  HANDS: { column: 2, row: 4 },
  PRIMARY: { column: 3, row: 4 },
  SECONDARY: { column: 4, row: 4 },
  FINGER_1: { column: 2, row: 5 },
  LEGS: { column: 3, row: 5 },
  FINGER_2: { column: 4, row: 5 },
  POWER_SOURCE: { column: 1, row: 6 },
  WAIST: { column: 3, row: 6 },
  AMMO: { column: 5, row: 6 },
  FEET: { column: 3, row: 7 },
}

export function EquipmentPaperdoll({ equipment, server }: EquipmentPaperdollProps) {
  const slots = orderedSlots(equipment)
  const equippedCount = equippedItemCount(equipment)

  return (
    <div className="min-w-0 rounded-xl border bg-card p-4 shadow-sm" aria-label="Equipment paperdoll">
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-base font-semibold">Equipment Paperdoll</h3>
          <p className="text-sm text-muted-foreground">
            EQ-style slot layout with duplicated ears, wrists, and fingers.
          </p>
        </div>
        <Badge variant="outline" className="rounded-md">
          {equippedCount}/{slots.length} equipped
        </Badge>
      </div>

      {equippedCount === 0 ? (
        <p className="mb-4 rounded-md border border-dashed p-3 text-sm text-muted-foreground">
          No equipment imported for {equipment.character_name}.
        </p>
      ) : null}

      <div className="max-w-full overflow-x-auto pb-1">
        <div
          className="grid min-w-[42rem] grid-cols-5 gap-2"
          style={{ gridTemplateRows: "repeat(7, minmax(7.25rem, max-content))", minHeight: "54rem" }}
          role="list"
        >
          {slots.map((slot) => (
            <EquipmentSlotCard key={slot.slot_key} slot={slot} server={server} />
          ))}
        </div>
      </div>
    </div>
  )
}

function EquipmentSlotCard({ slot, server }: { slot: CharacterEquipmentSlot; server: string }) {
  const placement = PAPERDOLL_PLACEMENTS[slot.slot_key]
  const style: CSSProperties | undefined = placement
    ? { gridColumn: placement.column, gridRow: placement.row }
    : undefined
  const item = slot.item
  const isSpecialImport = item ? isStarterOrNoTradeImport(item) : false

  return (
    <div
      role="listitem"
      aria-label={`${slot.label} slot`}
      style={style}
      className={cn(
        "min-h-[7.25rem] rounded-lg border bg-background/80 p-2 shadow-sm",
        item ? "border-border" : "border-dashed text-muted-foreground",
        isSpecialImport && "bg-muted/70 text-muted-foreground"
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[0.68rem] font-semibold uppercase tracking-wide text-muted-foreground">
          {slot.label}
        </span>
        {isSpecialImport ? (
          <Badge variant="secondary" className="h-4 rounded px-1 text-[0.62rem]">
            *
          </Badge>
        ) : null}
      </div>

      {item ? <EquipmentItem item={item} server={server} /> : <EmptySlot />}
    </div>
  )
}

function EquipmentItem({ item, server }: { item: CharacterEquipmentItem; server: string }) {
  const specialImport = isStarterOrNoTradeImport(item)

  return (
    <div className="grid gap-2">
      <div className="flex min-w-0 items-start gap-2">
        <ItemIcon item={item} />
        <div className="min-w-0">
          <ItemLink
            itemId={item.item_id}
            name={specialImport ? `${item.name} *` : item.name}
            server={server}
          />
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {item.slot_display ?? item.slot ?? item.item_type ?? "Slot unknown"}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1">
        {specialImport ? (
          <Badge variant="secondary" className="rounded-md">
            Starter / No Trade *
          </Badge>
        ) : null}
        {!item.enriched ? (
          <Badge variant="outline" className="rounded-md text-muted-foreground">
            {item.enrichment_status === "inventory_stub" ? "Inventory stub" : "Not enriched"}
          </Badge>
        ) : null}
        {!item.has_price ? (
          <Badge variant="outline" className="rounded-md text-muted-foreground">
            No price
          </Badge>
        ) : null}
      </div>

      <p className="text-xs text-muted-foreground">
        AC {item.stats.ac ?? "–"} · HP {item.stats.hp ?? "–"} · Mana {item.stats.mana ?? "–"}
      </p>
      <p className="text-xs text-muted-foreground">Market {formatPrice(item.price.market_price_pp)}</p>
    </div>
  )
}

function ItemIcon({ item }: { item: Pick<CharacterEquipmentItem, "icon_url" | "icon_id" | "name"> }) {
  if (item.icon_url) {
    return (
      <img
        src={item.icon_url}
        alt=""
        className="size-9 shrink-0 rounded-md border bg-muted object-cover"
        loading="lazy"
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-[0.62rem] font-semibold text-muted-foreground"
      title={item.icon_id ? `Icon ${item.icon_id}` : `No icon for ${item.name}`}
    >
      {item.icon_id ? `#${item.icon_id}` : item.name.slice(0, 2).toUpperCase()}
    </span>
  )
}

function EmptySlot() {
  return (
    <div className="flex min-h-[4.75rem] items-center justify-center rounded-md border border-dashed text-xs">
      Empty
    </div>
  )
}

function orderedSlots(equipment: CharacterEquipmentResponse): CharacterEquipmentSlot[] {
  const seen = new Set<string>()
  const slots: CharacterEquipmentSlot[] = []

  for (const slotKey of equipment.slot_order) {
    const slot = equipment.slots[slotKey]
    if (slot) {
      slots.push(slot)
      seen.add(slotKey)
    }
  }

  for (const [slotKey, slot] of Object.entries(equipment.slots)) {
    if (!seen.has(slotKey)) {
      slots.push(slot)
    }
  }

  return slots
}
