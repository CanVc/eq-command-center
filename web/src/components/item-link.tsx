import { useState } from "react"

import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import { cn } from "@/lib/utils"

export type ItemLinkDetail = {
  label: string
  value: string | null | undefined
}

type ItemLinkProps = {
  itemId: number | null
  name: string
  details?: ItemLinkDetail[]
  className?: string
}

export function ItemLink({ itemId, name, details = [], className }: ItemLinkProps) {
  const [open, setOpen] = useState(false)
  const hasItemId = itemId !== null && itemId !== undefined

  return (
    <HoverCard open={open} onOpenChange={setOpen} openDelay={100} closeDelay={150}>
      <HoverCardTrigger asChild>
        <a
          href={hasItemId ? `/items/${itemId}` : "#"}
          rel={hasItemId ? `eq:item:${itemId}` : undefined}
          aria-haspopup="dialog"
          onClick={(event) => {
            event.preventDefault()
            setOpen((current) => !current)
          }}
          className={cn(
            "font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
            className
          )}
        >
          {name}
        </a>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="w-72">
        <div className="grid gap-2">
          <div className="min-w-0">
            <p className="break-words text-sm font-semibold">{name}</p>
            <p className="text-xs text-muted-foreground">
              {hasItemId ? `Item ID ${itemId}` : "Unresolved item"}
            </p>
          </div>

          {details.length > 0 ? (
            <dl className="grid gap-1 border-t pt-2">
              {details.map((detail) => (
                <div key={detail.label} className="grid grid-cols-[6.5rem_1fr] gap-2 text-xs">
                  <dt className="text-muted-foreground">{detail.label}</dt>
                  <dd className="min-w-0 break-words font-medium">{detail.value || "n/a"}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="border-t pt-2 text-xs text-muted-foreground">
              More item stats will be available from the item tooltip flow.
            </p>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  )
}
