export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value)
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "n/a"
  }

  return `${formatNumber(value)}pp`
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "n/a"
  }

  return `${value.toFixed(1)}%`
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseDate(value)

  if (!date) {
    return "n/a"
  }

  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
    hour12: false,
  }).format(date)
}

export function formatTime(value: Date | string | number | null | undefined): string {
  const date = parseDate(value)

  if (!date) {
    return "n/a"
  }

  return new Intl.DateTimeFormat("fr-FR", {
    timeStyle: "short",
    hour12: false,
  }).format(date)
}

function parseDate(value: Date | string | number | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") {
    return null
  }

  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date
}
