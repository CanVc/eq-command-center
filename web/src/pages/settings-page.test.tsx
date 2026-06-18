import { describe, expect, it } from "vitest"

import type { SettingsStatusResponse } from "@/lib/api"
import { formatMageloStatusLabel, latestImportSummary } from "@/lib/settings"

describe("SettingsPage helpers", () => {
  it("presents Magelo as loaded or not loaded", () => {
    expect(formatMageloStatusLabel("loaded")).toBe("loaded")
    expect(formatMageloStatusLabel("idle")).toBe("not loaded")
    expect(formatMageloStatusLabel("loading")).toBe("not loaded")
    expect(formatMageloStatusLabel("unavailable")).toBe("not loaded")
  })

  it("summarizes the latest TLP Auctions import state", () => {
    expect(latestImportSummary(buildSettingsPayload())).toContain(
      "tlp_auctions_prices finished"
    )

    expect(latestImportSummary({ ...buildSettingsPayload(), latest_tlp_import: null })).toBe(
      "No TLP Auctions import has been recorded yet."
    )

    expect(latestImportSummary({ ...buildSettingsPayload(), import_runs_error: "no such table" })).toBe(
      "Import audit table could not be read."
    )
  })
})

function buildSettingsPayload(): SettingsStatusResponse {
  return {
    status: "ok",
    db_path: "C:/tmp/eqmarket.sqlite",
    default_server: "frostreaver",
    active_server: "mischief",
    latest_tlp_import: {
      import_run_id: 10,
      source_name: "tlp_auctions_prices",
      source_url: "server=mischief;mode=history;history_days=3",
      status: "completed",
      items_seen: 50,
      items_inserted: 2,
      items_updated: 12,
      error: null,
      started_at: "2026-06-16T09:59:00",
      finished_at: "2026-06-16T10:00:00",
    },
    recent_tlp_errors: [],
    import_runs_error: null,
    eq_log_path: "C:/EverQuest/Logs/eqlog_Dreadbank_frostreaver.txt",
    eq_log_exists: true,
    eq_log_import_state: null,
    log_settings_error: null,
  }
}
