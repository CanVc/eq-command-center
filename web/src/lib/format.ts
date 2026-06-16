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
  if (!value) {
    return "n/a"
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return "n/a"
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date)
}
