import { ThumbsDown, ThumbsUp } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ItemPreferenceStatus, ItemPreferenceStatusUpdate } from "@/lib/api"
import { cn } from "@/lib/utils"

export function ItemPreferenceActions({
  status,
  itemName,
  disabled = false,
  onChange,
}: {
  status: ItemPreferenceStatus | null
  itemName: string
  disabled?: boolean
  onChange: (status: ItemPreferenceStatusUpdate) => void
}) {
  const wanted = status === "wanted"
  const ignored = status === "ignored"

  return (
    <div className="flex shrink-0 items-center gap-1">
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        title={wanted ? "Remove wanted mark" : "Mark wanted"}
        aria-label={`${wanted ? "Remove wanted mark from" : "Mark wanted"} ${itemName}`}
        aria-pressed={wanted}
        disabled={disabled}
        className={cn(
          wanted && "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-300"
        )}
        onClick={() => onChange(wanted ? "neutral" : "wanted")}
      >
        <ThumbsUp aria-hidden="true" />
      </Button>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        title={ignored ? "Remove ignore mark" : "Ignore item"}
        aria-label={`${ignored ? "Remove ignore mark from" : "Ignore"} ${itemName}`}
        aria-pressed={ignored}
        disabled={disabled}
        className={cn(
          ignored && "border-red-500/50 bg-red-500/10 text-red-700 hover:bg-red-500/15 dark:text-red-300"
        )}
        onClick={() => onChange(ignored ? "neutral" : "ignored")}
      >
        <ThumbsDown aria-hidden="true" />
      </Button>
    </div>
  )
}

export function ItemPreferenceBadge({ status }: { status: ItemPreferenceStatus | null }) {
  if (status === "wanted") {
    return (
      <Badge variant="outline" className="rounded-md border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300">
        Wanted
      </Badge>
    )
  }

  if (status === "ignored") {
    return (
      <Badge variant="outline" className="rounded-md border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300">
        Ignored
      </Badge>
    )
  }

  return null
}
