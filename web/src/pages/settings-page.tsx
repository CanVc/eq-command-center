import {
  Activity,
  CheckCircle2,
  Database,
  FileClock,
  Server,
  TriangleAlert,
} from "lucide-react"
import type { ReactNode } from "react"

import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { LatestTlpImport, SettingsStatusResponse } from "@/lib/api"
import { formatDateTime, formatNumber } from "@/lib/format"
import type { MageloStatus } from "@/lib/magelo"
import { formatMageloStatusLabel, latestImportSummary } from "@/lib/settings"
import { cn } from "@/lib/utils"

type SettingsPageProps = {
  settings: SettingsStatusResponse
  mageloStatus: MageloStatus
}

export function SettingsPage({ settings, mageloStatus }: SettingsPageProps) {
  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Local Status</h2>
          <p className="text-sm text-muted-foreground">
            Read-only diagnostics for the local API, database, and import pipeline.
          </p>
        </div>
        <Badge variant="outline" className="rounded-md">
          read-only
        </Badge>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard
          title="API health"
          value={settings.status}
          description="Local FastAPI status endpoint is reachable."
          icon={<Activity aria-hidden="true" />}
          tone="emerald"
        />
        <StatusCard
          title="Database"
          value={settings.db_path}
          description="SQLite path currently configured by the API."
          icon={<Database aria-hidden="true" />}
          compact
        />
        <StatusCard
          title="Server"
          value={settings.active_server}
          description={`Default server: ${settings.default_server}`}
          icon={<Server aria-hidden="true" />}
        />
        <StatusCard
          title="Magelo"
          value={formatMageloStatusLabel(mageloStatus)}
          description="Native item tooltip script status in this browser."
          icon={
            mageloStatus === "loaded" ? (
              <CheckCircle2 aria-hidden="true" />
            ) : (
              <TriangleAlert aria-hidden="true" />
            )
          }
          tone={mageloStatus === "loaded" ? "emerald" : "amber"}
        />
      </div>

      <Card className="min-w-0">
        <CardHeader className="border-b">
          <CardTitle className="flex items-center gap-2">
            <FileClock aria-hidden="true" className="size-4" />
            <h3>Last TLP Auctions Import</h3>
          </CardTitle>
          <CardDescription>{latestImportSummary(settings)}</CardDescription>
          <CardAction>
            <ImportStatusBadge
              status={settings.latest_tlp_import?.status}
              hasError={settings.import_runs_error !== null}
            />
          </CardAction>
        </CardHeader>
        <CardContent>
          {settings.latest_tlp_import ? (
            <ImportDetails importRun={settings.latest_tlp_import} />
          ) : (
            <EmptyImportState error={settings.import_runs_error} />
          )}
        </CardContent>
      </Card>
    </section>
  )
}

function StatusCard({
  title,
  value,
  description,
  icon,
  tone = "neutral",
  compact = false,
}: {
  title: string
  value: string
  description: string
  icon: ReactNode
  tone?: "neutral" | "emerald" | "amber"
  compact?: boolean
}) {
  const toneClass = {
    neutral: "bg-muted/20 text-muted-foreground",
    emerald: "bg-emerald-500/10 text-emerald-700",
    amber: "bg-amber-500/10 text-amber-700",
  }[tone]

  return (
    <Card size="sm">
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className={cn("break-words", compact ? "text-base" : "text-2xl")}>
          {value}
        </CardTitle>
        <CardAction>
          <span className={cn("flex size-9 items-center justify-center rounded-md", toneClass)}>
            {icon}
          </span>
        </CardAction>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

function ImportDetails({ importRun }: { importRun: LatestTlpImport }) {
  return (
    <dl className="grid gap-2 md:grid-cols-2">
      <DetailRow label="Source" value={importRun.source_name} />
      <DetailRow label="Status" value={importRun.status} />
      <DetailRow label="Started" value={formatDateTime(importRun.started_at)} />
      <DetailRow label="Finished" value={formatDateTime(importRun.finished_at)} />
      <DetailRow label="Items seen" value={formatNumber(importRun.items_seen)} />
      <DetailRow label="Items inserted" value={formatNumber(importRun.items_inserted)} />
      <DetailRow label="Items updated" value={formatNumber(importRun.items_updated)} />
      <DetailRow label="Source URL" value={importRun.source_url ?? "n/a"} />
      {importRun.error ? <DetailRow label="Error" value={importRun.error} wide /> : null}
    </dl>
  )
}

function DetailRow({
  label,
  value,
  wide = false,
}: {
  label: string
  value: string
  wide?: boolean
}) {
  return (
    <div
      className={cn(
        "grid gap-1 rounded-md border bg-background px-3 py-2 sm:grid-cols-[8rem_1fr]",
        wide && "md:col-span-2"
      )}
    >
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words text-sm font-medium">{value}</dd>
    </div>
  )
}

function ImportStatusBadge({
  status,
  hasError,
}: {
  status: string | undefined
  hasError: boolean
}) {
  if (hasError) {
    return <Badge variant="destructive">unavailable</Badge>
  }

  if (!status) {
    return (
      <Badge variant="outline" className="rounded-md">
        none
      </Badge>
    )
  }

  return (
    <Badge
      variant="outline"
      className={cn(
        "rounded-md",
        status === "completed"
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700"
          : "border-amber-500/40 bg-amber-500/10 text-amber-700"
      )}
    >
      {status}
    </Badge>
  )
}

function EmptyImportState({ error }: { error: string | null }) {
  return (
    <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">
      {error ? `Import runs unavailable: ${error}` : "No TLP Auctions import found."}
    </p>
  )
}
