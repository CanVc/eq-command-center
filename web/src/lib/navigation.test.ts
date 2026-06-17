import { describe, expect, it } from "vitest"

import { activePageIdFromRoute, pageIdFromPath, pathForItemDetail, pathForPage, routeFromPath } from "./navigation"

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

  it("parses item detail routes while keeping the Items nav active", () => {
    const route = routeFromPath("/items/10895/")

    expect(route).toEqual({ kind: "item-detail", itemId: 10895 })
    expect(activePageIdFromRoute(route)).toBe("items")
    expect(pathForItemDetail(10895)).toBe("/items/10895")
  })
})
