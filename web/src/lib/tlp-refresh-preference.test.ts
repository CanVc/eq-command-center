import { describe, expect, it, vi } from "vitest"

import {
  DEFAULT_TLP_MAX_AGE_HOURS,
  MAX_TLP_MAX_AGE_HOURS,
  TLP_REFRESH_STORAGE_KEY,
  formatTlpMaxAgeHours,
  normalizeTlpMaxAgeHours,
  readTlpMaxAgeHours,
  saveTlpMaxAgeHours,
  type TlpRefreshStorage,
} from "./tlp-refresh-preference"

function createStorage(initialValue: string | null = null): TlpRefreshStorage {
  let value = initialValue

  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_, nextValue: string) => {
      value = nextValue
    }),
    removeItem: vi.fn(() => {
      value = null
    }),
  }
}

describe("TLP refresh preference", () => {
  it("normalizes invalid, negative, and oversized max age values", () => {
    expect(normalizeTlpMaxAgeHours("3.5")).toBe(3.5)
    expect(normalizeTlpMaxAgeHours("0")).toBe(0)
    expect(normalizeTlpMaxAgeHours(" ")).toBe(DEFAULT_TLP_MAX_AGE_HOURS)
    expect(normalizeTlpMaxAgeHours("nope")).toBe(DEFAULT_TLP_MAX_AGE_HOURS)
    expect(normalizeTlpMaxAgeHours(-1)).toBe(0)
    expect(normalizeTlpMaxAgeHours(9999)).toBe(MAX_TLP_MAX_AGE_HOURS)
  })

  it("formats max age values compactly", () => {
    expect(formatTlpMaxAgeHours(6)).toBe("6")
    expect(formatTlpMaxAgeHours(1.5)).toBe("1.5")
    expect(formatTlpMaxAgeHours(1.25)).toBe("1.25")
  })

  it("reads the preferred max age from storage", () => {
    const storage = createStorage("12")

    expect(readTlpMaxAgeHours(storage)).toBe(12)
    expect(storage.getItem).toHaveBeenCalledWith(TLP_REFRESH_STORAGE_KEY)
  })

  it("saves the normalized max age to storage", () => {
    const storage = createStorage()

    expect(saveTlpMaxAgeHours("0.5", storage)).toBe(0.5)
    expect(storage.setItem).toHaveBeenCalledWith(TLP_REFRESH_STORAGE_KEY, "0.5")
    expect(readTlpMaxAgeHours(storage)).toBe(0.5)
  })

  it("falls back to the default when storage throws", () => {
    const storage: TlpRefreshStorage = {
      getItem: vi.fn(() => {
        throw new Error("blocked")
      }),
      setItem: vi.fn(() => {
        throw new Error("blocked")
      }),
      removeItem: vi.fn(),
    }

    expect(readTlpMaxAgeHours(storage)).toBe(DEFAULT_TLP_MAX_AGE_HOURS)
    expect(saveTlpMaxAgeHours(24, storage)).toBe(24)
  })
})
