export const MAGELO_ITEM_ICON_BASE_URL = "https://www.magelocdn.com/images/eq/item_icones"
export const MAGELO_TOOLTIP_URL = "https://eq.magelo.com/tooltip.json"

const MAGELO_TOOLTIP_LOCALE = "en"
const MAGELO_TOOLTIP_TIMEOUT_MS = 10_000

const mageloTooltipIconIdCache = new Map<number, Promise<number | null>>()

type MageloTooltipPayload = {
  icon?: string | number | null
}

type JsonpCallback = (data: MageloTooltipPayload) => void

export function mageloItemIconUrl(iconId: number | null | undefined): string | null {
  if (!isPositiveNumber(iconId)) {
    return null
  }

  return `${MAGELO_ITEM_ICON_BASE_URL}/item_${iconId}.png`
}

export function resolveItemIconUrl(
  iconUrl: string | null | undefined,
  iconId: number | null | undefined
): string | null {
  const trimmedIconUrl = iconUrl?.trim()

  return trimmedIconUrl || mageloItemIconUrl(iconId)
}

export function fetchMageloTooltipIconId(itemId: number | null | undefined): Promise<number | null> {
  if (!isPositiveNumber(itemId)) {
    return Promise.resolve(null)
  }

  const cachedIconId = mageloTooltipIconIdCache.get(itemId)
  if (cachedIconId) {
    return cachedIconId
  }

  const iconIdPromise = requestMageloTooltipIconId(itemId)
  mageloTooltipIconIdCache.set(itemId, iconIdPromise)
  return iconIdPromise
}

function requestMageloTooltipIconId(itemId: number): Promise<number | null> {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return Promise.resolve(null)
  }

  return new Promise((resolve) => {
    const callbackName = mageloTooltipCallbackName(itemId)
    const callbacks = window as unknown as Record<string, JsonpCallback | undefined>
    const previousCallback = callbacks[callbackName]
    const script = document.createElement("script")
    let settled = false

    const settle = (iconId: number | null) => {
      if (settled) {
        return
      }

      settled = true
      window.clearTimeout(timeoutId)
      script.remove()

      if (previousCallback) {
        callbacks[callbackName] = previousCallback
      } else {
        delete callbacks[callbackName]
      }

      resolve(iconId)
    }

    callbacks[callbackName] = (data) => {
      try {
        previousCallback?.(data)
      } finally {
        settle(parseIconId(data.icon))
      }
    }

    script.async = true
    script.src = `${MAGELO_TOOLTIP_URL}?item=${encodeURIComponent(String(itemId))}`
    script.onerror = () => settle(null)
    const timeoutId = window.setTimeout(() => settle(null), MAGELO_TOOLTIP_TIMEOUT_MS)

    document.head.appendChild(script)
  })
}

function mageloTooltipCallbackName(itemId: number): string {
  return `jsonp_item_${itemId}_${MAGELO_TOOLTIP_LOCALE}`
}

function parseIconId(value: string | number | null | undefined): number | null {
  if (typeof value === "number") {
    return isPositiveNumber(value) ? value : null
  }

  if (typeof value !== "string") {
    return null
  }

  const parsed = Number(value)
  return isPositiveNumber(parsed) ? parsed : null
}

function isPositiveNumber(value: number | null | undefined): value is number {
  return value !== null && value !== undefined && Number.isFinite(value) && value > 0
}
