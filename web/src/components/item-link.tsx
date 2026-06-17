import { useEffect, useMemo, useRef, useState } from "react"
import type { MouseEvent } from "react"

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { fetchItemTooltip, type ItemTooltip } from "@/lib/api"
import { formatDateTime, formatNumber, formatPrice } from "@/lib/format"
import { getMageloStatus, subscribeMageloStatus, type MageloStatus } from "@/lib/magelo"
import { navigateToPath, pathForItemDetail } from "@/lib/navigation"
import { cn } from "@/lib/utils"

export type ItemLinkDetail = {
  label: string
  value: string | null | undefined
}

type ItemLinkProps = {
  itemId: number | null
  name: string
  server: string
  details?: ItemLinkDetail[]
  className?: string
}

type TooltipState =
  | { key: string; status: "idle" }
  | { key: string; status: "loading" }
  | { key: string; status: "ready"; tooltip: ItemTooltip }
  | { key: string; status: "error" }

export function ItemLink({ itemId, name, server, details = [], className }: ItemLinkProps) {
  const [open, setOpen] = useState(false)
  const [mageloStatus, setMageloStatus] = useState<MageloStatus>(() => getMageloStatus())
  const tooltipKey = `${server}:${itemId ?? "name"}:${name}`
  const [tooltipState, setTooltipState] = useState<TooltipState>({
    key: tooltipKey,
    status: "idle",
  })
  const requestIdRef = useRef(0)
  const hasItemId = itemId !== null && itemId !== undefined
  const shouldUseLocalFallback = !hasItemId || mageloStatus !== "loaded"
  const href = hasItemId ? pathForItemDetail(itemId) : "#"
  const currentTooltipState = useMemo<TooltipState>(() => {
    if (tooltipState.key === tooltipKey) {
      return tooltipState
    }

    return { key: tooltipKey, status: "idle" }
  }, [tooltipKey, tooltipState])

  useEffect(() => subscribeMageloStatus(setMageloStatus), [])

  const loadTooltip = async () => {
    if (currentTooltipState.status === "loading" || currentTooltipState.status === "ready") {
      return
    }

    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    setTooltipState({ key: tooltipKey, status: "loading" })

    try {
      const tooltip = await fetchItemTooltip({ itemId, name, server })

      if (requestIdRef.current === requestId) {
        setTooltipState({ key: tooltipKey, status: "ready", tooltip })
      }
    } catch {
      if (requestIdRef.current === requestId) {
        setTooltipState({ key: tooltipKey, status: "error" })
      }
    }
  }

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen)

    if (nextOpen) {
      void loadTooltip()
    }
  }

  const itemAnchor = (
    <a
      href={href}
      rel={hasItemId ? `eq:item:${itemId}` : undefined}
      aria-haspopup={shouldUseLocalFallback ? "dialog" : undefined}
      onClick={(event) => {
        if (hasItemId) {
          if (shouldHandleClientNavigation(event)) {
            event.preventDefault()
            navigateToPath(href)
          }
          return
        }

        event.preventDefault()
        if (shouldUseLocalFallback) {
          handleOpenChange(!open)
        }
      }}
      className={cn(
        "font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        className
      )}
    >
      {name}
    </a>
  )

  if (!shouldUseLocalFallback) {
    return itemAnchor
  }

  return (
    <HoverCard open={open} onOpenChange={handleOpenChange} openDelay={100} closeDelay={150}>
      <HoverCardTrigger asChild>{itemAnchor}</HoverCardTrigger>
      <HoverCardContent align="start" className="w-80 max-w-[calc(100vw-2rem)]">
        <ItemTooltipContent
          name={name}
          itemId={itemId}
          details={details}
          tooltipState={currentTooltipState}
        />
      </HoverCardContent>
    </HoverCard>
  )
}

function shouldHandleClientNavigation(event: MouseEvent<HTMLAnchorElement>): boolean {
  return (
    event.button === 0 &&
    !event.defaultPrevented &&
    !event.metaKey &&
    !event.altKey &&
    !event.ctrlKey &&
    !event.shiftKey
  )
}

function ItemTooltipContent({
  name,
  itemId,
  details,
  tooltipState,
}: {
  name: string
  itemId: number | null
  details: ItemLinkDetail[]
  tooltipState: TooltipState
}) {
  if (tooltipState.status === "ready") {
    return <ResolvedTooltip tooltip={tooltipState.tooltip} details={details} />
  }

  return (
    <div className="grid gap-2">
      <TooltipHeader name={name} itemId={itemId} subtitle={itemId ? "Loading local stats" : "Resolving by name"} />
      {details.length > 0 ? <DetailList details={details} /> : null}
      {tooltipState.status === "error" ? (
        <p className="border-t pt-2 text-xs text-muted-foreground">
          Local tooltip unavailable.
        </p>
      ) : (
        <p className="border-t pt-2 text-xs text-muted-foreground">Loading item tooltip...</p>
      )}
    </div>
  )
}

function ResolvedTooltip({ tooltip, details }: { tooltip: ItemTooltip; details: ItemLinkDetail[] }) {
  const statRows = [
    { label: "Slot", value: tooltip.slot },
    { label: "Classes", value: tooltip.classes },
    { label: "Flags", value: tooltip.flags },
    { label: "Stats", value: formatStatGroup([
      ["AC", tooltip.ac],
      ["HP", tooltip.hp],
      ["Mana", tooltip.mana],
      ["End", tooltip.endurance],
    ]) },
    { label: "Attributes", value: formatStatGroup([
      ["STR", tooltip.str],
      ["STA", tooltip.sta],
      ["AGI", tooltip.agi],
      ["DEX", tooltip.dex],
      ["WIS", tooltip.wis],
      ["INT", tooltip.int],
      ["CHA", tooltip.cha],
    ]) },
    { label: "Resists", value: formatStatGroup([
      ["MR", tooltip.sv_magic],
      ["FR", tooltip.sv_fire],
      ["CR", tooltip.sv_cold],
      ["PR", tooltip.sv_poison],
      ["DR", tooltip.sv_disease],
    ]) },
    { label: "Combat", value: formatCombatStats(tooltip) },
    { label: "Market price", value: formatPrice(tooltip.market_price_pp) },
    { label: "Last seen", value: formatLastSeen(tooltip) },
  ].filter((row) => row.value)
  const firstEffect = tooltip.effects.find((effect) => effect.description || effect.spell.name)

  return (
    <div className="grid gap-2">
      <TooltipHeader
        name={tooltip.name}
        itemId={tooltip.item_id}
        subtitle={tooltip.item_type ?? tooltip.server}
      />
      <dl className="grid gap-1 border-t pt-2">
        {statRows.map((detail) => (
          <DetailRow key={detail.label} label={detail.label} value={detail.value} />
        ))}
        {firstEffect ? (
          <DetailRow
            label="Effect"
            value={firstEffect.description ?? firstEffect.spell.name ?? null}
          />
        ) : null}
      </dl>
      {details.length > 0 ? <DetailList title="Listing" details={details} /> : null}
    </div>
  )
}

function TooltipHeader({
  name,
  itemId,
  subtitle,
}: {
  name: string
  itemId: number | null
  subtitle: string | null | undefined
}) {
  return (
    <div className="min-w-0">
      <p className="break-words text-sm font-semibold">{name}</p>
      <p className="text-xs text-muted-foreground">
        {itemId ? `Item ID ${itemId}` : subtitle ?? "Unresolved item"}
      </p>
    </div>
  )
}

function DetailList({
  details,
  title,
}: {
  details: ItemLinkDetail[]
  title?: string
}) {
  return (
    <dl className="grid gap-1 border-t pt-2">
      {title ? <dt className="text-xs font-medium text-muted-foreground">{title}</dt> : null}
      {details.map((detail) => (
        <DetailRow key={detail.label} label={detail.label} value={detail.value} />
      ))}
    </dl>
  )
}

function DetailRow({
  label,
  value,
}: {
  label: string
  value: string | null | undefined
}) {
  return (
    <div className="grid grid-cols-[6.5rem_1fr] gap-2 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words font-medium">{value || "n/a"}</dd>
    </div>
  )
}

function formatStatGroup(stats: Array<[string, number | null]>): string | null {
  const visibleStats = stats.filter(([, value]) => value !== null)

  if (visibleStats.length === 0) {
    return null
  }

  return visibleStats.map(([label, value]) => `${label} ${formatNumber(value as number)}`).join(" / ")
}

function formatCombatStats(tooltip: ItemTooltip): string | null {
  const parts = [
    tooltip.damage === null ? null : `DMG ${formatNumber(tooltip.damage)}`,
    tooltip.delay === null ? null : `Delay ${formatNumber(tooltip.delay)}`,
    tooltip.ratio === null ? null : `Ratio ${tooltip.ratio.toFixed(2)}`,
    tooltip.haste === null ? null : `Haste ${formatNumber(tooltip.haste)}%`,
  ].filter(Boolean)

  return parts.length > 0 ? parts.join(" / ") : null
}

function formatLastSeen(tooltip: ItemTooltip): string {
  if (tooltip.last_seen_pp === null) {
    return "n/a"
  }

  const seenAt = formatDateTime(tooltip.last_seen_at)
  return seenAt === "n/a" ? formatPrice(tooltip.last_seen_pp) : `${formatPrice(tooltip.last_seen_pp)} at ${seenAt}`
}
