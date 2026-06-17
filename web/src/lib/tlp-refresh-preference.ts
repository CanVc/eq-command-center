export const DEFAULT_TLP_MAX_AGE_HOURS = 6
export const MIN_TLP_MAX_AGE_HOURS = 0
export const MAX_TLP_MAX_AGE_HOURS = 24 * 30
export const TLP_REFRESH_STORAGE_KEY = "eq-command-center.tlp-max-age-hours"
export const DEFAULT_TLP_AUTO_REFRESH_ENABLED = false
export const TLP_AUTO_REFRESH_INTERVAL_MS = 5 * 60 * 1000
export const TLP_AUTO_REFRESH_STORAGE_KEY = "eq-command-center.tlp-auto-refresh"

export type TlpRefreshStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">

export function normalizeTlpMaxAgeHours(value: number | string | null | undefined): number {
  if (value === null || value === undefined) {
    return DEFAULT_TLP_MAX_AGE_HOURS
  }

  const rawValue = typeof value === "number" ? value : value.trim()

  if (rawValue === "") {
    return DEFAULT_TLP_MAX_AGE_HOURS
  }

  const parsedValue = typeof rawValue === "number" ? rawValue : Number(rawValue)

  if (!Number.isFinite(parsedValue)) {
    return DEFAULT_TLP_MAX_AGE_HOURS
  }

  const boundedValue = Math.min(
    MAX_TLP_MAX_AGE_HOURS,
    Math.max(MIN_TLP_MAX_AGE_HOURS, parsedValue)
  )

  return Math.round(boundedValue * 100) / 100
}

export function formatTlpMaxAgeHours(value: number): string {
  return normalizeTlpMaxAgeHours(value).toFixed(2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1")
}

export function readTlpMaxAgeHours(storage: TlpRefreshStorage | null = getBrowserStorage()): number {
  if (!storage) {
    return DEFAULT_TLP_MAX_AGE_HOURS
  }

  try {
    return normalizeTlpMaxAgeHours(storage.getItem(TLP_REFRESH_STORAGE_KEY))
  } catch {
    return DEFAULT_TLP_MAX_AGE_HOURS
  }
}

export function saveTlpMaxAgeHours(
  maxAgeHours: number | string,
  storage: TlpRefreshStorage | null = getBrowserStorage()
): number {
  const normalizedValue = normalizeTlpMaxAgeHours(maxAgeHours)

  if (!storage) {
    return normalizedValue
  }

  try {
    storage.setItem(TLP_REFRESH_STORAGE_KEY, formatTlpMaxAgeHours(normalizedValue))
  } catch {
    return normalizedValue
  }

  return normalizedValue
}

export function readTlpAutoRefreshEnabled(storage: TlpRefreshStorage | null = getBrowserStorage()): boolean {
  if (!storage) {
    return DEFAULT_TLP_AUTO_REFRESH_ENABLED
  }

  try {
    const storedValue = storage.getItem(TLP_AUTO_REFRESH_STORAGE_KEY)

    if (storedValue === "true") {
      return true
    }

    if (storedValue === "false") {
      return false
    }
  } catch {
    return DEFAULT_TLP_AUTO_REFRESH_ENABLED
  }

  return DEFAULT_TLP_AUTO_REFRESH_ENABLED
}

export function saveTlpAutoRefreshEnabled(
  enabled: boolean,
  storage: TlpRefreshStorage | null = getBrowserStorage()
): boolean {
  if (!storage) {
    return enabled
  }

  try {
    storage.setItem(TLP_AUTO_REFRESH_STORAGE_KEY, String(enabled))
  } catch {
    return enabled
  }

  return enabled
}

function getBrowserStorage(): TlpRefreshStorage | null {
  if (typeof window === "undefined") {
    return null
  }

  return window.localStorage
}
