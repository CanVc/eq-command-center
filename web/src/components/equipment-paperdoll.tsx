import type { CSSProperties } from "react"

import { ItemIcon } from "@/components/item-icon"
import { ItemLink } from "@/components/item-link"
import { Badge } from "@/components/ui/badge"
import type { CharacterEquipmentItem, CharacterEquipmentResponse, CharacterEquipmentSlot } from "@/lib/api"
import { equippedItemCount, isStarterOrNoTradeImport } from "@/lib/characters"
import { cn } from "@/lib/utils"

type EquipmentPaperdollProps = {
  equipment: CharacterEquipmentResponse
  server: string
}

type SlotPlacement = {
  column: number
  row: number
  columnSpan?: number
  rowSpan?: number
}

const CLASS_IMAGE_PLACEMENT: Required<SlotPlacement> = {
  column: 2,
  row: 2,
  columnSpan: 2,
  rowSpan: 4,
}

const PAPERDOLL_PLACEMENTS: Record<string, SlotPlacement> = {
  EAR_1: { column: 1, row: 1 },
  HEAD: { column: 2, row: 1 },
  FACE: { column: 3, row: 1 },
  EAR_2: { column: 4, row: 1 },
  CHEST: { column: 1, row: 2 },
  NECK: { column: 4, row: 2 },
  ARMS: { column: 1, row: 3 },
  BACK: { column: 4, row: 3 },
  WAIST: { column: 1, row: 4 },
  SHOULDERS: { column: 4, row: 4 },
  WRIST_1: { column: 1, row: 5 },
  WRIST_2: { column: 4, row: 5 },
  LEGS: { column: 1, row: 6 },
  HANDS: { column: 2, row: 6 },
  POWER_SOURCE: { column: 3, row: 6 },
  FEET: { column: 4, row: 6 },
  FINGER_1: { column: 2, row: 7 },
  FINGER_2: { column: 3, row: 7 },
  PRIMARY: { column: 1, row: 8 },
  SECONDARY: { column: 2, row: 8 },
  RANGE: { column: 3, row: 8 },
  AMMO: { column: 4, row: 8 },
}

export function EquipmentPaperdoll({ equipment, server }: EquipmentPaperdollProps) {
  const slots = orderedSlots(equipment)
  const placedSlots = slots.filter((slot) => PAPERDOLL_PLACEMENTS[slot.slot_key])
  const extraSlots = slots.filter((slot) => !PAPERDOLL_PLACEMENTS[slot.slot_key] && slot.item)
  const equippedCount = equippedItemCount(equipment)

  return (
    <div className="min-w-0 rounded-xl border bg-card p-4 shadow-sm" aria-label="Equipment paperdoll">
      <div className="mb-4 flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-base font-semibold">Equipment Paperdoll</h3>
          <p className="text-sm text-muted-foreground">
            In-game style slot layout with compact item icons and names.
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
          className="grid w-fit min-w-[19rem] gap-2 rounded-lg border bg-muted/20 p-2"
          style={{
            gridTemplateColumns: "repeat(4, minmax(4.25rem, 4.75rem))",
            gridTemplateRows: "repeat(8, minmax(4.5rem, auto))",
          }}
          role="list"
        >
          <ClassImageSlot characterName={equipment.character_name} />
          {placedSlots.map((slot) => (
            <EquipmentSlotCard key={slot.slot_key} slot={slot} server={server} />
          ))}
        </div>
      </div>

      {extraSlots.length > 0 ? (
        <div className="mt-3 grid w-fit grid-cols-2 gap-2 sm:grid-cols-4" role="list" aria-label="Additional equipment slots">
          {extraSlots.map((slot) => (
            <EquipmentSlotCard key={slot.slot_key} slot={slot} server={server} compact />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function ClassImageSlot({ characterName }: { characterName: string }) {
  return (
    <div
      aria-label={`Class image placeholder for ${characterName}`}
      className="flex min-h-[10rem] flex-col items-center justify-center rounded-md border border-dashed bg-background/60 p-3 text-center text-xs text-muted-foreground shadow-inner"
      style={placementStyle(CLASS_IMAGE_PLACEMENT)}
    >
      <span className="text-[0.68rem] font-semibold uppercase tracking-wide">Class image</span>
      <span className="mt-1 max-w-32">Placeholder for a future class portrait.</span>
    </div>
  )
}

function EquipmentSlotCard({
  slot,
  server,
  compact = false,
}: {
  slot: CharacterEquipmentSlot
  server: string
  compact?: boolean
}) {
  const placement = PAPERDOLL_PLACEMENTS[slot.slot_key]
  const style: CSSProperties | undefined = compact || !placement ? undefined : placementStyle(placement)
  const item = slot.item
  const isSpecialImport = item ? isStarterOrNoTradeImport(item) : false

  return (
    <div
      role="listitem"
      aria-label={`${slot.label} slot`}
      style={style}
      className={cn(
        "flex min-h-[4.5rem] min-w-0 flex-col rounded-md border bg-background/80 p-1 text-center shadow-sm",
        item ? "border-border" : "border-dashed text-muted-foreground",
        isSpecialImport && "bg-muted/70 text-muted-foreground"
      )}
    >
      <div className="mb-0.5 flex min-h-3 items-center justify-center gap-1">
        <span className="truncate text-[0.6rem] font-semibold uppercase tracking-wide text-muted-foreground">
          {slot.label}
        </span>
        {isSpecialImport ? (
          <span aria-hidden="true" className="text-[0.6rem] text-muted-foreground">
            *
          </span>
        ) : null}
      </div>

      {item ? <EquipmentItem item={item} server={server} /> : <EmptySlot />}
    </div>
  )
}

function EquipmentItem({ item, server }: { item: CharacterEquipmentItem; server: string }) {
  const specialImport = isStarterOrNoTradeImport(item)
  const name = specialImport ? `${item.name} *` : item.name

  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1">
      <ItemIcon
        iconUrl={item.icon_url}
        iconId={item.icon_id}
        itemId={item.item_id}
        name={item.name}
        className="size-8"
      />
      <div className="min-w-0 max-w-full" title={name}>
        <ItemLink
          itemId={item.item_id}
          name={name}
          server={server}
          className="block truncate text-[0.62rem] leading-tight"
        />
      </div>
    </div>
  )
}

function EmptySlot() {
  return (
    <div className="flex min-h-0 flex-1 items-center justify-center rounded border border-dashed px-1 text-[0.62rem]">
      Empty
    </div>
  )
}

function placementStyle(placement: SlotPlacement): CSSProperties {
  return {
    gridColumn: `${placement.column} / span ${placement.columnSpan ?? 1}`,
    gridRow: `${placement.row} / span ${placement.rowSpan ?? 1}`,
  }
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
