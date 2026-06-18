import { describe, expect, it } from "vitest"

import { formatMageloStatusLabel } from "@/lib/settings"

describe("SettingsPage helpers", () => {
  it("presents Magelo as loaded or not loaded", () => {
    expect(formatMageloStatusLabel("loaded")).toBe("loaded")
    expect(formatMageloStatusLabel("idle")).toBe("not loaded")
    expect(formatMageloStatusLabel("loading")).toBe("not loaded")
    expect(formatMageloStatusLabel("unavailable")).toBe("not loaded")
  })
})
