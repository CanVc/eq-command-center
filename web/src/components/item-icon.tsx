import { useEffect, useState } from "react"

import { fetchMageloTooltipIconId, resolveItemIconUrl } from "@/lib/item-icons"
import { cn } from "@/lib/utils"

type ItemIconProps = {
  iconUrl?: string | null
  iconId?: number | null
  itemId?: number | null
  name: string
  className?: string
}

type ResolvedMageloIcon = {
  itemId: number
  iconId: number | null
}

export function ItemIcon({ iconUrl, iconId, itemId, name, className }: ItemIconProps) {
  const [failedIconUrl, setFailedIconUrl] = useState<string | null>(null)
  const [resolvedMageloIcon, setResolvedMageloIcon] = useState<ResolvedMageloIcon | null>(null)
  const mageloIconId = resolvedMageloIcon && resolvedMageloIcon.itemId === itemId ? resolvedMageloIcon.iconId : null
  const effectiveIconId = iconId ?? mageloIconId
  const resolvedIconUrl = resolveItemIconUrl(iconUrl, effectiveIconId)

  useEffect(() => {
    if (iconId || iconUrl || !itemId) {
      return undefined
    }

    let active = true

    void fetchMageloTooltipIconId(itemId).then((fetchedIconId) => {
      if (active) {
        setResolvedMageloIcon({ itemId, iconId: fetchedIconId })
      }
    })

    return () => {
      active = false
    }
  }, [iconId, iconUrl, itemId])

  if (resolvedIconUrl && failedIconUrl !== resolvedIconUrl) {
    return (
      <img
        src={resolvedIconUrl}
        alt=""
        className={cn("size-9 shrink-0 rounded-md border bg-muted object-cover", className)}
        loading="lazy"
        title={effectiveIconId ? `Icon ${effectiveIconId}` : name}
        onError={() => setFailedIconUrl(resolvedIconUrl)}
      />
    )
  }

  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-[0.62rem] font-semibold text-muted-foreground",
        className
      )}
      title={effectiveIconId ? `Icon ${effectiveIconId}` : `No icon for ${name}`}
    >
      {effectiveIconId ? `#${effectiveIconId}` : fallbackInitials(name)}
    </span>
  )
}

function fallbackInitials(name: string): string {
  return name.slice(0, 2).toUpperCase() || "?"
}
