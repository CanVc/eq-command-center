import type { MageloStatus } from "@/lib/magelo"

export function formatMageloStatusLabel(status: MageloStatus): string {
  return status === "loaded" ? "loaded" : "not loaded"
}
