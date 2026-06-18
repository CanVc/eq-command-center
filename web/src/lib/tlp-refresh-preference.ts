export const DEFAULT_TLP_MAX_AGE_MINUTES = 6 * 60
export const MIN_TLP_MAX_AGE_MINUTES = 0
export const MAX_TLP_MAX_AGE_MINUTES = 24 * 30 * 60
export const TLP_REFRESH_STORAGE_KEY = "eq-command-center.tlp-max-age-minutes"
export const LEGACY_TLP_REFRESH_STORAGE_KEY = "eq-command-center.tlp-max-age-hours"

export const DEFAULT_TLP_AUTO_REFRESH_ENABLED = false
export const TLP_AUTO_REFRESH_STORAGE_KEY = "eq-command-center.tlp-auto-refresh"
export const DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES = 5
export const MIN_TLP_AUTO_REFRESH_INTERVAL_MINUTES = 1
export const MAX_TLP_AUTO_REFRESH_INTERVAL_MINUTES = 24 * 60
export const TLP_AUTO_REFRESH_INTERVAL_STORAGE_KEY = "eq-command-center.tlp-auto-refresh-interval-minutes"

export type TlpRefreshStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">

export function normalizeTlpMaxAgeMinutes(value: number | string | null | undefined): number {
  return normalizeMinuteValue(value, {
    defaultValue: DEFAULT_TLP_MAX_AGE_MINUTES,
    minValue: MIN_TLP_MAX_AGE_MINUTES,
    maxValue: MAX_TLP_MAX_AGE_MINUTES,
  })
}

export function formatTlpMaxAgeMinutes(value: number): string {
  return formatMinutes(normalizeTlpMaxAgeMinutes(value))
}

export function readTlpMaxAgeMinutes(storage: TlpRefreshStorage | null = getBrowserStorage()): number {
  if (!storage) {
    return DEFAULT_TLP_MAX_AGE_MINUTES
  }

  try {
    const storedValue = storage.getItem(TLP_REFRESH_STORAGE_KEY)
    if (storedValue !== null) {
      return normalizeTlpMaxAgeMinutes(storedValue)
    }

    const legacyHours = storage.getItem(LEGACY_TLP_REFRESH_STORAGE_KEY)
    if (legacyHours !== null) {
      const migratedValue = normalizeTlpMaxAgeMinutes(Number(legacyHours) * 60)
      storage.setItem(TLP_REFRESH_STORAGE_KEY, formatTlpMaxAgeMinutes(migratedValue))
      storage.removeItem(LEGACY_TLP_REFRESH_STORAGE_KEY)
      return migratedValue
    }
  } catch {
    return DEFAULT_TLP_MAX_AGE_MINUTES
  }

  return DEFAULT_TLP_MAX_AGE_MINUTES
}

export function saveTlpMaxAgeMinutes(
  maxAgeMinutes: number | string,
  storage: TlpRefreshStorage | null = getBrowserStorage()
): number {
  const normalizedValue = normalizeTlpMaxAgeMinutes(maxAgeMinutes)

  if (!storage) {
    return normalizedValue
  }

  try {
    storage.setItem(TLP_REFRESH_STORAGE_KEY, formatTlpMaxAgeMinutes(normalizedValue))
    storage.removeItem(LEGACY_TLP_REFRESH_STORAGE_KEY)
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

export function normalizeTlpAutoRefreshIntervalMinutes(value: number | string | null | undefined): number {
  return normalizeMinuteValue(value, {
    defaultValue: DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES,
    minValue: MIN_TLP_AUTO_REFRESH_INTERVAL_MINUTES,
    maxValue: MAX_TLP_AUTO_REFRESH_INTERVAL_MINUTES,
  })
}

export function formatTlpAutoRefreshIntervalMinutes(value: number): string {
  return formatMinutes(normalizeTlpAutoRefreshIntervalMinutes(value))
}

export function readTlpAutoRefreshIntervalMinutes(
  storage: TlpRefreshStorage | null = getBrowserStorage()
): number {
  if (!storage) {
    return DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES
  }

  try {
    return normalizeTlpAutoRefreshIntervalMinutes(storage.getItem(TLP_AUTO_REFRESH_INTERVAL_STORAGE_KEY))
  } catch {
    return DEFAULT_TLP_AUTO_REFRESH_INTERVAL_MINUTES
  }
}

export function saveTlpAutoRefreshIntervalMinutes(
  intervalMinutes: number | string,
  storage: TlpRefreshStorage | null = getBrowserStorage()
): number {
  const normalizedValue = normalizeTlpAutoRefreshIntervalMinutes(intervalMinutes)

  if (!storage) {
    return normalizedValue
  }

  try {
    storage.setItem(TLP_AUTO_REFRESH_INTERVAL_STORAGE_KEY, formatTlpAutoRefreshIntervalMinutes(normalizedValue))
  } catch {
    return normalizedValue
  }

  return normalizedValue
}

function normalizeMinuteValue(
  value: number | string | null | undefined,
  {
    defaultValue,
    minValue,
    maxValue,
  }: {
    defaultValue: number
    minValue: number
    maxValue: number
  }
): number {
  if (value === null || value === undefined) {
    return defaultValue
  }

  const rawValue = typeof value === "number" ? value : value.trim()

  if (rawValue === "") {
    return defaultValue
  }

  const parsedValue = typeof rawValue === "number" ? rawValue : Number(rawValue)

  if (!Number.isFinite(parsedValue)) {
    return defaultValue
  }

  const boundedValue = Math.min(maxValue, Math.max(minValue, parsedValue))
  return Math.round(boundedValue * 100) / 100
}

function formatMinutes(value: number): string {
  return value.toFixed(2).replace(/\.00$/, "").replace(/(\.\d)0$/, "$1")
}

function getBrowserStorage(): TlpRefreshStorage | null {
  if (typeof window === "undefined") {
    return null
  }

  return window.localStorage
}
