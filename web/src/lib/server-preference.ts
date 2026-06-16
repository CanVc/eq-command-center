export const DEFAULT_SERVER = "frostreaver"
export const SERVER_STORAGE_KEY = "eq-command-center.server"

export type ServerStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">

export function normalizeServer(value: string | null | undefined): string {
  const normalized = value?.trim().toLowerCase()
  return normalized || DEFAULT_SERVER
}

export function readPreferredServer(storage: ServerStorage | null = getBrowserStorage()): string {
  if (!storage) {
    return DEFAULT_SERVER
  }

  try {
    return normalizeServer(storage.getItem(SERVER_STORAGE_KEY))
  } catch {
    return DEFAULT_SERVER
  }
}

export function savePreferredServer(
  server: string,
  storage: ServerStorage | null = getBrowserStorage()
): string {
  const normalized = normalizeServer(server)

  if (!storage) {
    return normalized
  }

  try {
    storage.setItem(SERVER_STORAGE_KEY, normalized)
  } catch {
    return normalized
  }

  return normalized
}

function getBrowserStorage(): ServerStorage | null {
  if (typeof window === "undefined") {
    return null
  }

  return window.localStorage
}
