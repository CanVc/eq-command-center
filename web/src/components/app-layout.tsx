import { useEffect, useState } from "react"
import type { KeyboardEvent, ReactNode } from "react"
import {
  BarChart3,
  Box,
  LayoutDashboard,
  ListFilter,
  Moon,
  RefreshCw,
  Search,
  Settings,
  Sun,
} from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { APP_PAGES, pathForPage, type AppPageId } from "@/lib/navigation"
import {
  MAX_TLP_MAX_AGE_HOURS,
  MIN_TLP_MAX_AGE_HOURS,
  formatTlpMaxAgeHours,
} from "@/lib/tlp-refresh-preference"
import { cn } from "@/lib/utils"

type AppLayoutProps = {
  activePage: AppPageId
  pageTitle?: string
  server: string
  isRefreshing: boolean
  isTlpRefreshing: boolean
  tlpMaxAgeHours: number
  tlpAutoRefreshEnabled: boolean
  children: ReactNode
  onNavigate: (pageId: AppPageId) => void
  onServerChange: (server: string) => void
  onTlpMaxAgeHoursChange: (maxAgeHours: number) => number
  onTlpAutoRefreshEnabledChange: (enabled: boolean) => boolean
  onRefresh: () => void
  onTlpRefresh: () => void
}

const SERVER_OPTIONS = [
  { value: "frostreaver", label: "Frostreaver" },
  { value: "mischief", label: "Mischief" },
  { value: "thornblade", label: "Thornblade" },
  { value: "oakwynd", label: "Oakwynd" },
]

const NAV_ICONS: Record<AppPageId, ReactNode> = {
  dashboard: <LayoutDashboard aria-hidden="true" />,
  deals: <BarChart3 aria-hidden="true" />,
  market: <ListFilter aria-hidden="true" />,
  items: <Search aria-hidden="true" />,
  settings: <Settings aria-hidden="true" />,
}

const THEME_STORAGE_KEY = "eq-command-center.theme"

type Theme = "light" | "dark"

export function AppLayout({
  activePage,
  pageTitle,
  server,
  isRefreshing,
  isTlpRefreshing,
  tlpMaxAgeHours,
  tlpAutoRefreshEnabled,
  children,
  onNavigate,
  onServerChange,
  onTlpMaxAgeHoursChange,
  onTlpAutoRefreshEnabledChange,
  onRefresh,
  onTlpRefresh,
}: AppLayoutProps) {
  const activePageDefinition = APP_PAGES.find((page) => page.id === activePage) ?? APP_PAGES[0]
  const title = pageTitle ?? activePageDefinition.title
  const [theme, setTheme] = useState<Theme>(() => getInitialTheme())

  useEffect(() => {
    applyTheme(theme)
    saveTheme(theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((current) => (current === "dark" ? "light" : "dark"))
  }

  const applyTlpMaxAgeInput = (input: HTMLInputElement) => {
    const rawValue = input.value.trim()
    const parsedValue = rawValue === "" ? Number.NaN : Number(rawValue)

    if (!Number.isFinite(parsedValue)) {
      input.value = formatTlpMaxAgeHours(tlpMaxAgeHours)
      return
    }

    const savedMaxAgeHours = onTlpMaxAgeHoursChange(parsedValue)
    input.value = formatTlpMaxAgeHours(savedMaxAgeHours)
  }

  const handleTlpMaxAgeKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.currentTarget.blur()
    }
  }

  return (
    <div className="min-h-svh bg-background text-foreground">
      <div className="grid min-h-svh lg:grid-cols-[16rem_1fr]">
        <aside className="hidden border-r bg-sidebar/70 lg:flex lg:flex-col">
          <div className="flex h-16 items-center gap-3 border-b px-5">
            <div className="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <Box aria-hidden="true" className="size-4" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold">EQ Command Center</p>
              <p className="truncate text-xs text-muted-foreground">Local market console</p>
            </div>
          </div>
          <nav className="flex flex-1 flex-col gap-1 p-3" aria-label="Primary">
            {APP_PAGES.map((page) => (
              <NavLink
                key={page.id}
                pageId={page.id}
                active={page.id === activePage}
                onNavigate={onNavigate}
              />
            ))}
          </nav>
        </aside>

        <div className="flex min-w-0 flex-col">
          <header className="sticky top-0 z-20 border-b bg-background/95 backdrop-blur">
            <div className="flex min-h-16 flex-col gap-3 px-4 py-3 sm:px-6 lg:h-16 lg:flex-row lg:items-center lg:justify-between lg:px-8 lg:py-0">
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-normal text-muted-foreground">
                  {server}
                </p>
                <h1 className="truncate text-xl font-semibold">{title}</h1>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Select value={server} onValueChange={onServerChange}>
                  <SelectTrigger aria-label="Server" className="h-9 w-[10.5rem]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SERVER_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <ThemeToggle theme={theme} onToggle={toggleTheme} />

                <label
                  className="flex h-9 items-center gap-1.5 rounded-md border border-input bg-background px-2 text-xs text-muted-foreground"
                  title="Maximum age, in hours, before a TLP item price is considered stale. Use 0 to refresh every eligible recent item."
                >
                  <span className="whitespace-nowrap">TLP max age</span>
                  <input
                    aria-label="TLP max age hours"
                    className="h-7 w-16 rounded-md border border-input bg-background px-2 text-right text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                    type="number"
                    min={MIN_TLP_MAX_AGE_HOURS}
                    max={MAX_TLP_MAX_AGE_HOURS}
                    step={0.5}
                    key={tlpMaxAgeHours}
                    defaultValue={formatTlpMaxAgeHours(tlpMaxAgeHours)}
                    disabled={isTlpRefreshing}
                    onBlur={(event) => applyTlpMaxAgeInput(event.currentTarget)}
                    onKeyDown={handleTlpMaxAgeKeyDown}
                  />
                  <span>h</span>
                </label>

                <label
                  className="flex h-9 items-center gap-2 rounded-md border border-input bg-background px-2.5 text-sm text-foreground"
                  title="Automatically start a stale TLP price refresh every 5 minutes. Empty auto runs skip Krono refresh."
                >
                  <input
                    aria-label="Auto-refresh TLP prices every 5 minutes"
                    className="size-4 accent-foreground"
                    type="checkbox"
                    checked={tlpAutoRefreshEnabled}
                    onChange={(event) => onTlpAutoRefreshEnabledChange(event.target.checked)}
                  />
                  <span className="whitespace-nowrap">Auto 5m</span>
                </label>

                <Button
                  type="button"
                  variant="outline"
                  onClick={onTlpRefresh}
                  disabled={isRefreshing || isTlpRefreshing}
                  title="Refresh stale item prices from TLP Auctions"
                >
                  <RefreshCw className={cn(isTlpRefreshing && "animate-spin")} />
                  TLP prices
                </Button>

                <Button type="button" onClick={onRefresh} disabled={isRefreshing}>
                  <RefreshCw className={cn(isRefreshing && !isTlpRefreshing && "animate-spin")} />
                  Refresh
                </Button>
              </div>
            </div>

            <nav
              className="flex gap-1 overflow-x-auto border-t px-3 py-2 lg:hidden"
              aria-label="Primary"
            >
              {APP_PAGES.map((page) => (
                <NavLink
                  key={page.id}
                  pageId={page.id}
                  active={page.id === activePage}
                  compact
                  onNavigate={onNavigate}
                />
              ))}
            </nav>
          </header>

          <main className="flex-1 px-4 py-5 sm:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </div>
  )
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const isDark = theme === "dark"

  return (
    <Button
      type="button"
      variant="outline"
      size="icon-lg"
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      onClick={onToggle}
    >
      {isDark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
    </Button>
  )
}

function NavLink({
  pageId,
  active,
  compact = false,
  onNavigate,
}: {
  pageId: AppPageId
  active: boolean
  compact?: boolean
  onNavigate: (pageId: AppPageId) => void
}) {
  const page = APP_PAGES.find((candidate) => candidate.id === pageId)

  if (!page) {
    return null
  }

  return (
    <a
      href={pathForPage(pageId)}
      aria-current={active ? "page" : undefined}
      onClick={(event) => {
        event.preventDefault()
        onNavigate(pageId)
      }}
      className={cn(
        "inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 [&_svg]:size-4",
        active && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
        compact && "shrink-0"
      )}
    >
      {NAV_ICONS[pageId]}
      <span>{page.label}</span>
    </a>
  )
}

function getInitialTheme(): Theme {
  if (typeof window === "undefined") {
    return "light"
  }

  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY)

    if (storedTheme === "light" || storedTheme === "dark") {
      return storedTheme
    }
  } catch {
    // Ignore storage errors and fall back to the system preference.
  }

  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ? "dark" : "light"
}

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") {
    return
  }

  document.documentElement.classList.toggle("dark", theme === "dark")
}

function saveTheme(theme: Theme) {
  if (typeof window === "undefined") {
    return
  }

  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Ignore storage errors; the in-memory toggle still works.
  }
}
