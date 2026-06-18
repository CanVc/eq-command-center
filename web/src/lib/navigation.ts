export type AppPageId = "dashboard" | "deals" | "market" | "items" | "interface" | "settings"

export type AppRoute =
  | { kind: "page"; pageId: AppPageId }
  | { kind: "item-detail"; itemId: number }

export type AppPageDefinition = {
  id: AppPageId
  label: string
  path: string
  title: string
  description: string
}

export const APP_PAGES: AppPageDefinition[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    path: "/",
    title: "Dashboard",
    description: "Market pulse for the active server.",
  },
  {
    id: "deals",
    label: "Deals",
    path: "/deals",
    title: "Deals",
    description: "Discounted listings ranked by market reference.",
  },
  {
    id: "market",
    label: "Market",
    path: "/market",
    title: "Market",
    description: "Recent auction listings and parser output.",
  },
  {
    id: "items",
    label: "Items",
    path: "/items",
    title: "Items",
    description: "Known item records from the local database.",
  },
  {
    id: "interface",
    label: "Interface",
    path: "/interface",
    title: "Interface",
    description: "TLP Auctions and EQ log parser controls.",
  },
  {
    id: "settings",
    label: "Settings",
    path: "/settings",
    title: "Settings",
    description: "Local API and application settings.",
  },
]

const PAGE_BY_PATH = new Map(APP_PAGES.map((page) => [page.path, page.id]))

const ITEM_DETAIL_PATH_RE = /^\/items\/(\d+)$/

export function routeFromPath(pathname: string): AppRoute {
  const normalizedPath = normalizePath(pathname)
  const itemMatch = normalizedPath.match(ITEM_DETAIL_PATH_RE)

  if (itemMatch) {
    return { kind: "item-detail", itemId: Number(itemMatch[1]) }
  }

  return { kind: "page", pageId: pageIdFromPath(normalizedPath) }
}

export function activePageIdFromRoute(route: AppRoute): AppPageId {
  return route.kind === "item-detail" ? "items" : route.pageId
}

export function pageIdFromPath(pathname: string): AppPageId {
  const normalizedPath = normalizePath(pathname)
  return PAGE_BY_PATH.get(normalizedPath) ?? "dashboard"
}

export function pathForPage(pageId: AppPageId): string {
  return APP_PAGES.find((page) => page.id === pageId)?.path ?? "/"
}

export function pathForItemDetail(itemId: number): string {
  return `/items/${itemId}`
}

export function navigateToPath(path: string): void {
  if (typeof window === "undefined") {
    return
  }

  if (window.location.pathname !== path) {
    window.history.pushState(null, "", path)
  }

  const event =
    typeof PopStateEvent === "function" ? new PopStateEvent("popstate") : new Event("popstate")
  window.dispatchEvent(event)
}

function normalizePath(pathname: string): string {
  const path = pathname.trim().replace(/\/+$/, "") || "/"
  return path === "" ? "/" : path
}
