export type AppPageId = "dashboard" | "deals" | "market" | "items" | "settings"

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
    id: "settings",
    label: "Settings",
    path: "/settings",
    title: "Settings",
    description: "Local API and interface preferences.",
  },
]

const PAGE_BY_PATH = new Map(APP_PAGES.map((page) => [page.path, page.id]))

export function pageIdFromPath(pathname: string): AppPageId {
  const normalizedPath = normalizePath(pathname)
  return PAGE_BY_PATH.get(normalizedPath) ?? "dashboard"
}

export function pathForPage(pageId: AppPageId): string {
  return APP_PAGES.find((page) => page.id === pageId)?.path ?? "/"
}

function normalizePath(pathname: string): string {
  const path = pathname.trim().replace(/\/+$/, "") || "/"
  return path === "" ? "/" : path
}
