import { describe, expect, it } from "vitest"

import { formatDateTime, formatNumber, formatPercent, formatPrice, formatTime } from "./format"

describe("format helpers", () => {
  it("formats market numbers and prices", () => {
    expect(formatNumber(16000)).toBe("16,000")
    expect(formatPrice(16000)).toBe("16,000pp")
  })

  it("uses n/a for missing price, percent, and date values", () => {
    expect(formatPrice(null)).toBe("n/a")
    expect(formatPercent(undefined)).toBe("n/a")
    expect(formatDateTime("")).toBe("n/a")
    expect(formatDateTime("not-a-date")).toBe("n/a")
  })

  it("formats percentages with one decimal place", () => {
    expect(formatPercent(75)).toBe("75.0%")
  })

  it("formats dates and refresh times with French 24-hour time", () => {
    const formattedDate = formatDateTime("2026-06-16T10:05:00")
    const formattedTime = formatTime(new Date("2026-06-16T22:15:30"))

    expect(formattedDate).toContain("10:05")
    expect(formattedDate).not.toMatch(/\b(?:AM|PM)\b/i)
    expect(formattedTime).toContain("22:15")
    expect(formattedTime).not.toMatch(/\b(?:AM|PM)\b/i)
  })
})
