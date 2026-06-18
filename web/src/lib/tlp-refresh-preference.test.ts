import { describe, expect, it, vi } from "vitest"

import {
  DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES,
  DEFAULT_TLP_MAX_AGE_MINUTES,
  LEGACY_TLP_REFRESH_STORAGE_KEY,
  MAX_TLP_MAX_AGE_MINUTES,
  TLP_AUTO_REFRESH_INTERVAL_STORAGE_KEY,
  TLP_AUTO_REFRESH_STORAGE_KEY,
  TLP_REFRESH_STORAGE_KEY,
  formatTlpAutoRefreshIntervalMinutes,
  formatTlpMaxAgeMinutes,
  normalizeTlpAutoRefreshIntervalMinutes,
  normalizeTlpMaxAgeMinutes,
  readTlpAutoRefreshEnabled,
  readTlpAutoRefreshIntervalMinutes,
  readTlpMaxAgeMinutes,
  saveTlpAutoRefreshEnabled,
  saveTlpAutoRefreshIntervalMinutes,
  saveTlpMaxAgeMinutes,
  type TlpRefreshStorage,
} from "./tlp-refresh-preference"

function createStorage(initialValues: Record<string, string | null> = {}): TlpRefreshStorage {
  const values = new Map<string, string>()

  for (const [key, value] of Object.entries(initialValues)) {
    if (value !== null) {
      values.set(key, value)
    }
  }

  return {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, nextValue: string) => {
      values.set(key, nextValue)
    }),
    removeItem: vi.fn((key: string) => {
      values.delete(key)
    }),
  }
}

describe("TLP refresh preference", () => {
  it("normalizes invalid, negative, and oversized max age minute values", () => {
    expect(normalizeTlpMaxAgeMinutes("90.5")).toBe(90.5)
    expect(normalizeTlpMaxAgeMinutes("0")).toBe(0)
    expect(normalizeTlpMaxAgeMinutes(" ")).toBe(DEFAULT_TLP_MAX_AGE_MINUTES)
    expect(normalizeTlpMaxAgeMinutes("nope")).toBe(DEFAULT_TLP_MAX_AGE_MINUTES)
    expect(normalizeTlpMaxAgeMinutes(-1)).toBe(0)
    expect(normalizeTlpMaxAgeMinutes(999999)).toBe(MAX_TLP_MAX_AGE_MINUTES)
  })

  it("formats max age minute values compactly", () => {
    expect(formatTlpMaxAgeMinutes(360)).toBe("360")
    expect(formatTlpMaxAgeMinutes(90.5)).toBe("90.5")
    expect(formatTlpMaxAgeMinutes(1.25)).toBe("1.25")
  })

  it("reads the preferred max age in minutes from storage", () => {
    const storage = createStorage({ [TLP_REFRESH_STORAGE_KEY]: "120" })

    expect(readTlpMaxAgeMinutes(storage)).toBe(120)
    expect(storage.getItem).toHaveBeenCalledWith(TLP_REFRESH_STORAGE_KEY)
  })

  it("migrates the legacy hours preference to minutes", () => {
    const storage = createStorage({ [LEGACY_TLP_REFRESH_STORAGE_KEY]: "1.5" })

    expect(readTlpMaxAgeMinutes(storage)).toBe(90)
    expect(storage.setItem).toHaveBeenCalledWith(TLP_REFRESH_STORAGE_KEY, "90")
    expect(storage.removeItem).toHaveBeenCalledWith(LEGACY_TLP_REFRESH_STORAGE_KEY)
  })

  it("saves the normalized max age to storage", () => {
    const storage = createStorage()

    expect(saveTlpMaxAgeMinutes("30.5", storage)).toBe(30.5)
    expect(storage.setItem).toHaveBeenCalledWith(TLP_REFRESH_STORAGE_KEY, "30.5")
    expect(storage.removeItem).toHaveBeenCalledWith(LEGACY_TLP_REFRESH_STORAGE_KEY)
    expect(readTlpMaxAgeMinutes(storage)).toBe(30.5)
  })

  it("reads and saves the auto-refresh enabled preference", () => {
    const storage = createStorage({ [TLP_AUTO_REFRESH_STORAGE_KEY]: "true" })

    expect(readTlpAutoRefreshEnabled(storage)).toBe(true)
    expect(storage.getItem).toHaveBeenCalledWith(TLP_AUTO_REFRESH_STORAGE_KEY)
    expect(saveTlpAutoRefreshEnabled(false, storage)).toBe(false)
    expect(storage.setItem).toHaveBeenCalledWith(TLP_AUTO_REFRESH_STORAGE_KEY, "false")
    expect(readTlpAutoRefreshEnabled(storage)).toBe(false)
  })

  it("reads and saves the auto-refresh interval in minutes", () => {
    const storage = createStorage({ [TLP_AUTO_REFRESH_INTERVAL_STORAGE_KEY]: "15" })

    expect(readTlpAutoRefreshIntervalMinutes(storage)).toBe(15)
    expect(normalizeTlpAutoRefreshIntervalMinutes(0)).toBe(1)
    expect(normalizeTlpAutoRefreshIntervalMinutes("nope")).toBe(DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES)
    expect(formatTlpAutoRefreshIntervalMinutes(2.5)).toBe("2.5")
    expect(saveTlpAutoRefreshIntervalMinutes("10", storage)).toBe(10)
    expect(storage.setItem).toHaveBeenCalledWith(TLP_AUTO_REFRESH_INTERVAL_STORAGE_KEY, "10")
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

    expect(readTlpMaxAgeMinutes(storage)).toBe(DEFAULT_TLP_MAX_AGE_MINUTES)
    expect(saveTlpMaxAgeMinutes(24, storage)).toBe(24)
    expect(readTlpAutoRefreshEnabled(storage)).toBe(false)
    expect(saveTlpAutoRefreshEnabled(true, storage)).toBe(true)
    expect(readTlpAutoRefreshIntervalMinutes(storage)).toBe(DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES)
    expect(saveTlpAutoRefreshIntervalMinutes(10, storage)).toBe(10)
  })
})
