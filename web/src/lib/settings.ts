import type { SettingsStatusResponse } from "@/lib/api"
import { formatDateTime } from "@/lib/format"
import type { MageloStatus } from "@/lib/magelo"

export function formatMageloStatusLabel(status: MageloStatus): string {
  return status === "loaded" ? "loaded" : "not loaded"
}

export function latestImportSummary(settings: SettingsStatusResponse): string {
  if (settings.import_runs_error) {
    return "Import audit table could not be read."
  }

  if (!settings.latest_tlp_import) {
    return "No TLP Auctions import has been recorded yet."
  }

  return `${settings.latest_tlp_import.source_name} finished ${formatDateTime(
    settings.latest_tlp_import.finished_at ?? settings.latest_tlp_import.started_at
  )}.`
}
