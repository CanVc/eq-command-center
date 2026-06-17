export const MAGELO_SCRIPT_SRC = "https://www.magelocdn.com/pack/eq/en/magelo-bar.js#3"

export type MageloStatus = "idle" | "loading" | "loaded" | "unavailable"

type MagelobarApi = {
  scan?: () => void
}

declare global {
  interface Window {
    Magelobar?: MagelobarApi
    __eqCommandCenterMageloStatus?: MageloStatus
  }
}

const MAGELO_SCRIPT_URL = "https://www.magelocdn.com/pack/eq/en/magelo-bar.js"
const MAGELO_INIT_CHECKS = 20
const MAGELO_INIT_RETRY_MS = 100
const listeners = new Set<(status: MageloStatus) => void>()

let currentStatus: MageloStatus = "idle"

export function getMageloStatus(): MageloStatus {
  if (currentStatus !== "unavailable" && hasMageloScanner()) {
    return "loaded"
  }

  return currentStatus
}

export function subscribeMageloStatus(listener: (status: MageloStatus) => void): () => void {
  listeners.add(listener)
  listener(getMageloStatus())

  return () => {
    listeners.delete(listener)
  }
}

export function ensureMageloScript(): MageloStatus {
  if (typeof window === "undefined" || typeof document === "undefined") {
    setMageloStatus("unavailable")
    return "unavailable"
  }

  if (currentStatus !== "unavailable" && hasMageloScanner()) {
    setMageloStatus("loaded")
    return "loaded"
  }

  if (currentStatus === "loading") {
    return currentStatus
  }

  const existingScript = findMageloScript()
  const script = existingScript ?? document.createElement("script")

  script.type = "text/javascript"
  script.async = true
  script.src = MAGELO_SCRIPT_SRC

  script.addEventListener("load", () => markLoadedIfScannerExists(), { once: true })
  script.addEventListener("error", () => setMageloStatus("unavailable"), { once: true })

  if (!existingScript) {
    document.head.appendChild(script)
  }

  setMageloStatus("loading")
  return currentStatus
}

export function scanMageloItems(): boolean {
  if (!hasMageloScanner()) {
    return false
  }

  try {
    window.Magelobar?.scan?.()
    setMageloStatus("loaded")
    return true
  } catch {
    setMageloStatus("unavailable")
    return false
  }
}

function markLoadedIfScannerExists(attempt = 0) {
  if (hasMageloScanner()) {
    setMageloStatus("loaded")
    return
  }

  if (attempt >= MAGELO_INIT_CHECKS) {
    setMageloStatus("unavailable")
    return
  }

  window.setTimeout(() => {
    markLoadedIfScannerExists(attempt + 1)
  }, MAGELO_INIT_RETRY_MS)
}

function hasMageloScanner(): boolean {
  return typeof window !== "undefined" && typeof window.Magelobar?.scan === "function"
}

function findMageloScript(): HTMLScriptElement | undefined {
  return Array.from(document.scripts).find((script) => script.src.startsWith(MAGELO_SCRIPT_URL))
}

function setMageloStatus(status: MageloStatus) {
  currentStatus = status

  if (typeof window !== "undefined") {
    window.__eqCommandCenterMageloStatus = status
  }

  for (const listener of listeners) {
    listener(status)
  }
}
