import { describe, expect, it } from "vitest"

import { pageIdFromPath, pathForPage } from "./navigation"

describe("navigation", () => {
  it("maps known paths to pages", () => {
    expect(pageIdFromPath("/")).toBe("dashboard")
    expect(pageIdFromPath("/deals")).toBe("deals")
    expect(pageIdFromPath("/market/")).toBe("market")
    expect(pageIdFromPath("/items")).toBe("items")
    expect(pageIdFromPath("/settings")).toBe("settings")
  })

  it("falls back unknown paths to the dashboard", () => {
    expect(pageIdFromPath("/not-built-yet")).toBe("dashboard")
  })

  it("returns stable page paths", () => {
    expect(pathForPage("dashboard")).toBe("/")
    expect(pathForPage("deals")).toBe("/deals")
    expect(pathForPage("market")).toBe("/market")
    expect(pathForPage("items")).toBe("/items")
    expect(pathForPage("settings")).toBe("/settings")
  })
})
