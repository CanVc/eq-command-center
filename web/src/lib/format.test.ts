import { describe, expect, it } from "vitest"

import { formatDateTime, formatNumber, formatPercent, formatPrice } from "./format"

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
})
