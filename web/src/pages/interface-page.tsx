import { AlertTriangle, FileWarning, RefreshCw, RotateCcw, Settings2 } from "lucide-react"
import { useState } from "react"
import type { FormEvent } from "react"

import { ItemLink } from "@/components/item-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { InterfacePageData, MarkTlpPricesStaleResult } from "@/lib/api"
import { formatDateTime, formatNumber } from "@/lib/format"
import {
  MAX_TLP_AUTO_REFRESH_INTERVAL_MINUTES,
  MAX_TLP_MAX_AGE_MINUTES,
  MIN_TLP_AUTO_REFRESH_INTERVAL_MINUTES,
  MIN_TLP_MAX_AGE_MINUTES,
  formatTlpAutoRefreshIntervalMinutes,
  formatTlpMaxAgeMinutes,
} from "@/lib/tlp-refresh-preference"
import { cn } from "@/lib/utils"

type InterfacePageProps = {
  data: InterfacePageData
  server: string
  tlpMaxAgeMinutes: number
  tlpAutoRefreshEnabled: boolean
  tlpAutoRefreshIntervalMinutes: number
  isTlpRefreshing: boolean
  onTlpMaxAgeMinutesChange: (maxAgeMinutes: number) => number
  onTlpAutoRefreshEnabledChange: (enabled: boolean) => boolean
  onTlpAutoRefreshIntervalMinutesChange: (intervalMinutes: number) => number
  onTlpRefresh: (options?: { maxAgeMinutes?: number; refreshKronoWhenEmpty?: boolean }) => void
  onFullRescan: () => Promise<MarkTlpPricesStaleResult>
}

export function InterfacePage({
  data,
  server,
  tlpMaxAgeMinutes,
  tlpAutoRefreshEnabled,
  tlpAutoRefreshIntervalMinutes,
  isTlpRefreshing,
  onTlpMaxAgeMinutesChange,
  onTlpAutoRefreshEnabledChange,
  onTlpAutoRefreshIntervalMinutesChange,
  onTlpRefresh,
  onFullRescan,
}: InterfacePageProps) {
  return (
    <Tabs defaultValue="items" className="gap-4">
      <TabsList>
        <TabsTrigger value="items">Items / TLP Auctions</TabsTrigger>
        <TabsTrigger value="logs">Auctions / EQ log</TabsTrigger>
      </TabsList>

      <TabsContent value="items" className="grid gap-4">
        <TlpControlsCard
          server={server}
          tlpMaxAgeMinutes={tlpMaxAgeMinutes}
          tlpAutoRefreshEnabled={tlpAutoRefreshEnabled}
          tlpAutoRefreshIntervalMinutes={tlpAutoRefreshIntervalMinutes}
          isTlpRefreshing={isTlpRefreshing}
          onTlpMaxAgeMinutesChange={onTlpMaxAgeMinutesChange}
          onTlpAutoRefreshEnabledChange={onTlpAutoRefreshEnabledChange}
          onTlpAutoRefreshIntervalMinutesChange={onTlpAutoRefreshIntervalMinutesChange}
          onTlpRefresh={onTlpRefresh}
          onFullRescan={onFullRescan}
        />
        <TlpErrorsCard data={data} server={server} />
      </TabsContent>

      <TabsContent value="logs" className="grid gap-4">
        <LogParseIssuesCard data={data} />
      </TabsContent>
    </Tabs>
  )
}

function TlpControlsCard({
  server,
  tlpMaxAgeMinutes,
  tlpAutoRefreshEnabled,
  tlpAutoRefreshIntervalMinutes,
  isTlpRefreshing,
  onTlpMaxAgeMinutesChange,
  onTlpAutoRefreshEnabledChange,
  onTlpAutoRefreshIntervalMinutesChange,
  onTlpRefresh,
  onFullRescan,
}: Omit<InterfacePageProps, "data">) {
  const [maxAgeInput, setMaxAgeInput] = useState(() => formatTlpMaxAgeMinutes(tlpMaxAgeMinutes))
  const [intervalInput, setIntervalInput] = useState(() => formatTlpAutoRefreshIntervalMinutes(tlpAutoRefreshIntervalMinutes))
  const [fullRescanState, setFullRescanState] = useState<"idle" | "running" | "done" | "error">("idle")
  const [fullRescanMessage, setFullRescanMessage] = useState<string | null>(null)

  const saveControls = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const savedMaxAge = onTlpMaxAgeMinutesChange(Number(maxAgeInput))
    const savedInterval = onTlpAutoRefreshIntervalMinutesChange(Number(intervalInput))
    setMaxAgeInput(formatTlpMaxAgeMinutes(savedMaxAge))
    setIntervalInput(formatTlpAutoRefreshIntervalMinutes(savedInterval))
  }

  const startFullRescan = async () => {
    setFullRescanState("running")
    setFullRescanMessage(null)

    try {
      const result = await onFullRescan()
      setFullRescanState("done")
      setFullRescanMessage(
        `${formatNumber(result.affected_count)} TLP price rows marked stale for ${result.server}. Refresh started.`
      )
      onTlpRefresh({ maxAgeMinutes: 0, refreshKronoWhenEmpty: false })
    } catch (error) {
      setFullRescanState("error")
      setFullRescanMessage(error instanceof Error ? error.message : "Unable to mark TLP prices stale.")
    }
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Settings2 aria-hidden="true" className="size-4" />
          <h3>TLP refresh configuration</h3>
        </CardTitle>
        <CardDescription>
          Configure stale-price detection in minutes for {server}. Auto-refresh uses the same settings and skips Krono-only runs when no item is stale.
        </CardDescription>
        <CardAction>
          <Badge variant="outline" className="rounded-md">
            {tlpAutoRefreshEnabled ? `auto ${formatTlpAutoRefreshIntervalMinutes(tlpAutoRefreshIntervalMinutes)}m` : "manual"}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-4">
        <form onSubmit={saveControls} className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">TLP max age minutes</span>
            <input
              aria-label="TLP max age minutes"
              className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              type="number"
              min={MIN_TLP_MAX_AGE_MINUTES}
              max={MAX_TLP_MAX_AGE_MINUTES}
              step={1}
              value={maxAgeInput}
              disabled={isTlpRefreshing}
              onChange={(event) => setMaxAgeInput(event.target.value)}
            />
          </label>
          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">Auto interval minutes</span>
            <input
              aria-label="TLP auto refresh interval minutes"
              className="h-9 rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              type="number"
              min={MIN_TLP_AUTO_REFRESH_INTERVAL_MINUTES}
              max={MAX_TLP_AUTO_REFRESH_INTERVAL_MINUTES}
              step={1}
              value={intervalInput}
              disabled={isTlpRefreshing}
              onChange={(event) => setIntervalInput(event.target.value)}
            />
          </label>
          <div className="flex items-end">
            <Button type="submit" className="w-full md:w-auto" disabled={isTlpRefreshing}>
              Save
            </Button>
          </div>
          <label className="flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm md:col-span-3">
            <input
              aria-label="Auto-refresh TLP prices"
              className="size-4 accent-foreground"
              type="checkbox"
              checked={tlpAutoRefreshEnabled}
              onChange={(event) => onTlpAutoRefreshEnabledChange(event.target.checked)}
            />
            <span>Auto-refresh TLP item prices every {formatTlpAutoRefreshIntervalMinutes(tlpAutoRefreshIntervalMinutes)} minutes</span>
          </label>
        </form>

        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => onTlpRefresh()} disabled={isTlpRefreshing}>
            <RefreshCw className={cn(isTlpRefreshing && "animate-spin")} />
            Refresh stale TLP prices
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => void startFullRescan()}
            disabled={isTlpRefreshing || fullRescanState === "running"}
          >
            <RotateCcw className={cn(fullRescanState === "running" && "animate-spin")} />
            Full rescan
          </Button>
        </div>

        {fullRescanMessage ? (
          <p className={cn("text-sm", fullRescanState === "error" ? "text-destructive" : "text-muted-foreground")}>
            {fullRescanMessage}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}

function TlpErrorsCard({ data, server }: { data: InterfacePageData; server: string }) {
  const { tlpErrors } = data

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle aria-hidden="true" className="size-4" />
          <h3>Active TLP item refresh errors</h3>
        </CardTitle>
        <CardDescription>
          Errors are shown only while the item is still stale or marked failed for {server}.
        </CardDescription>
        <CardAction>
          <Badge variant={tlpErrors.active_error_count > 0 ? "destructive" : "outline"}>
            {formatNumber(tlpErrors.active_error_count)} active
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-4">
        <dl className="grid gap-2 md:grid-cols-3">
          <SummaryTile label="Stale items" value={formatNumber(tlpErrors.stale_item_count)} />
          <SummaryTile label="Max age" value={`${formatTlpMaxAgeMinutes(tlpErrors.max_age_minutes)} min`} />
          <SummaryTile
            label="Latest TLP import"
            value={tlpErrors.latest_tlp_import ? tlpErrors.latest_tlp_import.status : "none"}
          />
        </dl>

        {tlpErrors.active_errors.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Item</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Seen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tlpErrors.active_errors.map((error, index) => (
                <TableRow key={`${error.import_run_id ?? "marker"}-${error.item_id}-${index}`}>
                  <TableCell className="font-medium">
                    <ItemLink itemId={error.item_id} name={error.item_name ?? `Item ${error.item_id}`} server={server} />
                  </TableCell>
                  <TableCell className="min-w-[14rem]">
                    <p className="break-words text-destructive">{error.error ?? "Unknown TLP Auctions error"}</p>
                    {error.source_url ? <p className="mt-1 break-words text-xs text-muted-foreground">{error.source_url}</p> : null}
                  </TableCell>
                  <TableCell>
                    <div className="grid gap-1 text-xs text-muted-foreground">
                      <span>{error.origin === "import_run" ? "failed import" : "failed marker"}</span>
                      <span>{error.price_source ?? "missing price"}</span>
                    </div>
                  </TableCell>
                  <TableCell>{formatDateTime(error.finished_at ?? error.started_at ?? error.latest_listing_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState label="No active item-level TLP refresh errors for this server." />
        )}
      </CardContent>
    </Card>
  )
}

function LogParseIssuesCard({ data }: { data: InterfacePageData }) {
  const { logParseIssues } = data

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <FileWarning aria-hidden="true" className="size-4" />
          <h3>EQ log parse issues</h3>
        </CardTitle>
        <CardDescription>
          Auction log lines or listing fragments that were imported but could not become fully usable market data.
        </CardDescription>
        <CardAction>
          <Badge variant={logParseIssues.issue_count > 0 ? "secondary" : "outline"}>
            {formatNumber(logParseIssues.issue_count)} shown
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent>
        {logParseIssues.issues.length > 0 ? (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Seller</TableHead>
                <TableHead>Reason</TableHead>
                <TableHead>Raw line</TableHead>
                <TableHead>Seen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logParseIssues.issues.map((issue) => (
                <TableRow key={issue.id}>
                  <TableCell>{formatDateTime(issue.timestamp ?? issue.last_seen_at)}</TableCell>
                  <TableCell>{issue.seller ?? "n/a"}</TableCell>
                  <TableCell>
                    <div className="grid gap-1">
                      <span className="font-medium">{issue.reason_code}</span>
                      <span className="text-xs text-muted-foreground">{issue.reason}</span>
                    </div>
                  </TableCell>
                  <TableCell className="max-w-[24rem] break-words text-xs">{issue.raw_line}</TableCell>
                  <TableCell>{formatNumber(issue.seen_count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ) : (
          <EmptyState label="No EQ log parse issues have been recorded for this server." />
        )}
      </CardContent>
    </Card>
  )
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-background px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm font-semibold">{value}</dd>
    </div>
  )
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{label}</p>
}
