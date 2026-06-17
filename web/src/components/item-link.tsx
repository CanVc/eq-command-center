import type { MouseEvent } from "react"

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

export function ItemLink({ itemId, name, className }: ItemLinkProps) {
  const hasItemId = itemId !== null && itemId !== undefined
  const href = hasItemId ? pathForItemDetail(itemId) : "#"

  return (
    <a
      href={href}
      rel={hasItemId ? `eq:item:${itemId}` : undefined}
      onClick={(event) => {
        if (hasItemId) {
          if (shouldHandleClientNavigation(event)) {
            event.preventDefault()
            navigateToPath(href)
          }
          return
        }

        event.preventDefault()
      }}
      className={cn(
        "font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
        className
      )}
    >
      {name}
    </a>
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
