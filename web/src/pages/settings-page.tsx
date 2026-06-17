import {
  Activity,
  CheckCircle2,
  Database,
  FileClock,
  FileText,
  Server,
  TriangleAlert,
} from "lucide-react"
import { useEffect, useState } from "react"
import type { FormEvent, ReactNode } from "react"

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
import type { EqLogSettings, LatestTlpImport, SettingsStatusResponse } from "@/lib/api"
import { ApiError, browseEqLogPath, updateEqLogPath } from "@/lib/api"
import { formatDateTime, formatNumber } from "@/lib/format"
import type { MageloStatus } from "@/lib/magelo"
import { formatMageloStatusLabel, latestImportSummary } from "@/lib/settings"
import { cn } from "@/lib/utils"

type SettingsPageProps = {
  settings: SettingsStatusResponse
  mageloStatus: MageloStatus
}

export function SettingsPage({ settings, mageloStatus }: SettingsPageProps) {
  const [logSettings, setLogSettings] = useState<EqLogSettings>(() => settings)

  useEffect(() => {
    setLogSettings(settings)
  }, [settings])

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
          local settings
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

      <LogPathCard
        server={settings.active_server}
        logSettings={logSettings}
        onLogSettingsChange={setLogSettings}
      />

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

function LogPathCard({
  server,
  logSettings,
  onLogSettingsChange,
}: {
  server: string
  logSettings: EqLogSettings
  onLogSettingsChange: (settings: EqLogSettings) => void
}) {
  const [draftPath, setDraftPath] = useState(logSettings.eq_log_path ?? "")
  const [saveState, setSaveState] = useState<"idle" | "browsing" | "saving" | "saved" | "error">("idle")
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    setDraftPath(logSettings.eq_log_path ?? "")
  }, [logSettings.eq_log_path])

  const saveLogPath = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    await persistLogPath(() => updateEqLogPath(server, draftPath), "saving")
  }

  const browseLogPath = async () => {
    await persistLogPath(() => browseEqLogPath(server), "browsing")
  }

  const persistLogPath = async (
    action: () => Promise<EqLogSettings>,
    pendingState: "browsing" | "saving"
  ) => {
    setSaveState(pendingState)
    setErrorMessage(null)

    try {
      const nextSettings = await action()
      onLogSettingsChange(nextSettings)
      setDraftPath(nextSettings.eq_log_path ?? "")
      setSaveState("saved")
    } catch (error) {
      setErrorMessage(formatLogPathError(error, pendingState))
      setSaveState("error")
    }
  }

  const statusLabel = logSettings.eq_log_path
    ? logSettings.eq_log_exists
      ? "found"
      : "missing"
    : "not configured"

  return (
    <Card className="min-w-0">
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <FileText aria-hidden="true" className="size-4" />
          <h3>EverQuest Log File</h3>
        </CardTitle>
        <CardDescription>
          Choose the local `eqlog_*.txt` used by CLI imports. Use Browse to open a native file picker, or paste the full path.
        </CardDescription>
        <CardAction>
          <Badge
            variant="outline"
            className={cn(
              "rounded-md",
              logSettings.eq_log_exists === true && "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
              logSettings.eq_log_exists === false && "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
            )}
          >
            {statusLabel}
          </Badge>
        </CardAction>
      </CardHeader>
      <CardContent className="grid gap-3">
        <form onSubmit={saveLogPath} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto_auto]">
          <label className="grid gap-1.5 text-sm">
            <span className="text-xs font-medium text-muted-foreground">Log path</span>
            <input
              aria-label="EverQuest log path"
              className="h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              value={draftPath}
              placeholder="C:\\...\\EverQuest\\Logs\\eqlog_Character_server.txt"
              onChange={(event) => {
                setDraftPath(event.target.value)
                setSaveState("idle")
                setErrorMessage(null)
              }}
            />
          </label>
          <div className="flex items-end">
            <Button
              type="button"
              variant="outline"
              disabled={saveState === "browsing" || saveState === "saving"}
              className="w-full md:w-auto"
              onClick={() => void browseLogPath()}
            >
              {saveState === "browsing" ? "Opening" : "Browse"}
            </Button>
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={saveState === "browsing" || saveState === "saving"} className="w-full md:w-auto">
              {saveState === "saving" ? "Saving" : "Save"}
            </Button>
          </div>
        </form>

        {saveState === "saved" ? (
          <p className="text-xs text-emerald-700 dark:text-emerald-300">Log path saved.</p>
        ) : saveState === "error" ? (
          <p className="text-xs text-destructive">{errorMessage ?? "Unable to update the log path."}</p>
        ) : null}

        <dl className="grid gap-2 md:grid-cols-2">
          <DetailRow label="Configured path" value={logSettings.eq_log_path ?? "n/a"} wide />
          <DetailRow label="Exists" value={logSettings.eq_log_exists === null ? "n/a" : logSettings.eq_log_exists ? "yes" : "no"} />
          <DetailRow label="Last offset" value={logSettings.eq_log_import_state ? formatNumber(logSettings.eq_log_import_state.last_position) : "n/a"} />
          <DetailRow label="Last import state" value={logSettings.eq_log_import_state ? formatDateTime(logSettings.eq_log_import_state.updated_at) : "n/a"} />
          {logSettings.log_settings_error ? (
            <DetailRow label="Error" value={logSettings.log_settings_error} wide />
          ) : null}
        </dl>
      </CardContent>
    </Card>
  )
}

function formatLogPathError(
  error: unknown,
  pendingState: "browsing" | "saving"
): string {
  if (pendingState === "browsing" && error instanceof ApiError && error.status === 404) {
    return "Unable to open the file picker: backend endpoint is missing. Restart the API, then refresh this page."
  }

  if (pendingState === "browsing" && error instanceof ApiError && error.status === 503) {
    return `Unable to open the file picker: ${error.message}. You can still paste the path manually.`
  }

  const prefix = pendingState === "browsing" ? "Unable to open the file picker" : "Unable to save the log path"
  const detail = error instanceof Error ? `: ${error.message}` : ""
  return `${prefix}${detail}`
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
    emerald: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    amber: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
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
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          : "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
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
