import { useEffect, useState } from "react"
import { Copy } from "lucide-react"

import { Button } from "@/components/ui/button"
import { copyText } from "@/lib/clipboard"
import { cn } from "@/lib/utils"

export function RawSalePanel({
  rawLine,
  className,
}: {
  rawLine: string | null | undefined
  className?: string
}) {
  const [copied, setCopied] = useState(false)
  const hasRawLine = rawLine !== null && rawLine !== undefined && rawLine !== ""

  useEffect(() => {
    if (!copied) {
      return undefined
    }

    const timer = window.setTimeout(() => {
      setCopied(false)
    }, 1500)

    return () => {
      window.clearTimeout(timer)
    }
  }, [copied])

  const copyRawLine = async () => {
    if (!hasRawLine) {
      return
    }

    await copyText(rawLine)
    setCopied(true)
  }

  return (
    <div className={cn("grid gap-2 rounded-md border bg-background p-3", className)}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Raw sale</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={!hasRawLine}
          onClick={() => void copyRawLine()}
        >
          <Copy aria-hidden="true" />
          {copied ? "Copied" : "Copy raw"}
        </Button>
      </div>
      <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted/40 p-3 font-mono text-xs leading-relaxed">
        {hasRawLine ? rawLine : "Raw unavailable for this sale."}
      </pre>
    </div>
  )
}
