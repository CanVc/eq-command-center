import { AlertTriangle, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

export function LoadingState({ title }: { title: string }) {
  return (
    <section
      aria-label={`${title} loading`}
      className="rounded-lg border bg-card p-4 text-card-foreground"
    >
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 aria-hidden="true" className="size-4 animate-spin" />
        <span>Loading {title}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
        <Skeleton className="h-20" />
      </div>
      <Skeleton className="mt-4 h-48" />
    </section>
  )
}

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title: string
  message: string
  onRetry: () => void
}) {
  return (
    <section
      aria-label={`${title} error`}
      className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-card-foreground"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-destructive">
            <AlertTriangle aria-hidden="true" className="size-4" />
            <span>Unable to load {title}</span>
          </div>
          <p className="break-words text-sm text-muted-foreground">{message}</p>
        </div>
        <Button type="button" variant="outline" onClick={onRetry}>
          Retry
        </Button>
      </div>
    </section>
  )
}
