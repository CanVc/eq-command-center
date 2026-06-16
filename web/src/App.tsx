import { useCallback, useEffect, useState } from "react"
import type { ReactNode } from "react"
import { Activity, Database, Loader2, RefreshCw } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { fetchHealth, type HealthResponse } from "@/lib/api"

type HealthState =
  | { status: "idle" | "loading" }
  | { status: "ready"; data: HealthResponse }
  | { status: "error"; message: string }

function App() {
  const [health, setHealth] = useState<HealthState>({ status: "loading" })

  const checkHealth = useCallback(async () => {
    setHealth({ status: "loading" })

    try {
      const data = await fetchHealth()
      setHealth({ status: "ready", data })
    } catch (error) {
      setHealth({
        status: "error",
        message: error instanceof Error ? error.message : "Unknown API error",
      })
    }
  }, [])

  useEffect(() => {
    let isActive = true

    async function loadInitialHealth() {
      try {
        const data = await fetchHealth()
        if (isActive) {
          setHealth({ status: "ready", data })
        }
      } catch (error) {
        if (isActive) {
          setHealth({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown API error",
          })
        }
      }
    }

    void loadInitialHealth()

    return () => {
      isActive = false
    }
  }, [])

  const isLoading = health.status === "loading" || health.status === "idle"
  const isReady = health.status === "ready"

  return (
    <main className="min-h-svh bg-background text-foreground">
      <section className="mx-auto flex min-h-svh w-full max-w-5xl items-center px-6 py-10">
        <Card className="w-full rounded-lg border-border/80 shadow-sm">
          <CardHeader className="gap-4 border-b">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="space-y-2">
                <Badge
                  variant={isReady ? "default" : health.status === "error" ? "destructive" : "secondary"}
                  className="rounded-md"
                >
                  {isReady ? "API connected" : health.status === "error" ? "API unavailable" : "Checking API"}
                </Badge>
                <div>
                  <CardTitle className="text-2xl">EQ Command Center</CardTitle>
                  <CardDescription>Local dashboard shell</CardDescription>
                </div>
              </div>
              <Button type="button" onClick={checkHealth} disabled={isLoading}>
                {isLoading ? <Loader2 className="animate-spin" /> : <RefreshCw />}
                Check API
              </Button>
            </div>
          </CardHeader>
          <CardContent className="grid gap-4 py-6 sm:grid-cols-3">
            <StatusTile
              icon={<Activity aria-hidden="true" />}
              label="Health"
              value={isReady ? health.data.status : health.status === "error" ? "error" : "pending"}
              loading={isLoading}
            />
            <StatusTile
              icon={<Database aria-hidden="true" />}
              label="SQLite"
              value={isReady ? health.data.db_path : health.status === "error" ? health.message : "waiting"}
              loading={isLoading}
            />
            <StatusTile
              label="Frontend"
              value="Vite + shadcn/ui"
              loading={false}
            />
          </CardContent>
        </Card>
      </section>
    </main>
  )
}

function StatusTile({
  icon,
  label,
  value,
  loading,
}: {
  icon?: ReactNode
  label: string
  value: string
  loading: boolean
}) {
  return (
    <div className="min-w-0 rounded-lg border bg-muted/20 p-4">
      <div className="mb-3 flex items-center gap-2 text-sm text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      {loading ? (
        <Skeleton className="h-5 w-2/3" />
      ) : (
        <p className="truncate text-sm font-medium text-foreground" title={value}>
          {value}
        </p>
      )}
    </div>
  )
}

export default App
