import type { ItemDetail, ItemListing, ItemSource, TlpHistoryPoint } from "@/lib/api"

export type PriceHistoryPoint = {
  sourceId: string
  timestamp: string
  price_pp: number
  price_raw: string | null
  seller: string | null
  source: string
}

export type ExternalItemLink = {
  label: string
  href: string
}

export function itemSourceLabel(source: ItemSource): string {
  const zone = cleanSourcePart(source.zone)
  const npc = cleanSourcePart(source.npc_name)

  if (zone && npc) {
    return `${zone} - ${npc}`
  }
  if (zone) {
    return zone
  }
  if (npc) {
    return npc
  }

  return cleanSourcePart(source.source_area) ?? cleanSourcePart(source.content_type) ?? source.data_source
}

export function primaryItemSourceLabel(sources: readonly ItemSource[] | null | undefined): string | null {
  return sources && sources.length > 0 ? itemSourceLabel(sources[0]) : null
}

export function buildPriceHistory(listings: ItemListing[]): PriceHistoryPoint[] {
  return listings
    .filter((listing) => listing.price_pp !== null)
    .map((listing) => ({
      sourceId: `listing:${listing.listing_id}`,
      timestamp: listing.timestamp,
      price_pp: listing.price_pp as number,
      price_raw: listing.price_raw,
      seller: listing.seller,
      source: listing.source,
    }))
    .sort((left, right) => {
      const timestampDelta = timestampValue(left.timestamp) - timestampValue(right.timestamp)
      return timestampDelta === 0 ? left.sourceId.localeCompare(right.sourceId) : timestampDelta
    })
}

export function buildTlpPriceHistory(points: TlpHistoryPoint[]): PriceHistoryPoint[] {
  return points
    .filter((point) => point.price_pp > 0)
    .map((point, index) => ({
      sourceId: `tlp:${point.timestamp}:${index}`,
      timestamp: point.timestamp,
      price_pp: point.price_pp,
      price_raw: formatTlpRawPrice(point),
      seller: point.seller,
      source: point.source,
    }))
    .sort((left, right) => {
      const timestampDelta = timestampValue(left.timestamp) - timestampValue(right.timestamp)
      return timestampDelta === 0 ? left.sourceId.localeCompare(right.sourceId) : timestampDelta
    })
}

export function latestPricedListing(listings: ItemListing[]): ItemListing | null {
  return [...listings]
    .filter((listing) => listing.price_pp !== null)
    .sort((left, right) => {
      const timestampDelta = timestampValue(right.timestamp) - timestampValue(left.timestamp)
      return timestampDelta === 0 ? right.listing_id - left.listing_id : timestampDelta
    })[0] ?? null
}

export function formatKronoEquivalent(
  pricePp: number | null | undefined,
  kronoPricePp: number | null | undefined
): string {
  if (!pricePp || !kronoPricePp || pricePp <= 0 || kronoPricePp <= 0) {
    return "n/a"
  }

  const krono = pricePp / kronoPricePp
  const precision = krono >= 10 ? 1 : 2
  return `${krono.toFixed(precision)} Krono`
}

export function buildExternalItemLinks(item: ItemDetail, server: string): ExternalItemLink[] {
  const tlpServer = encodeURIComponent(server.trim().toLowerCase() || "frostreaver")
  const itemName = encodeURIComponent(item.name)

  return [
    {
      label: "Lucy",
      href: `https://lucy.allakhazam.com/item.html?id=${item.item_id}`,
    },
    {
      label: "Magelo",
      href: `https://eq.magelo.com/item/${item.item_id}`,
    },
    {
      label: "TLP Auctions",
      href: `https://www.tlp-auctions.com/search/${tlpServer}/${itemName}`,
    },
  ]
}

function timestampValue(value: string): number {
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? 0 : parsed
}

function cleanSourcePart(value: string | null | undefined): string | null {
  const trimmed = value?.trim()
  return trimmed ? trimmed : null
}

function formatTlpRawPrice(point: TlpHistoryPoint): string {
  const parts: string[] = []
  if (point.krono_price > 0) {
    parts.push(`${formatCompactNumber(point.krono_price)} krono`)
  }
  if (point.plat_price > 0) {
    parts.push(`${formatCompactNumber(point.plat_price)}pp`)
  }
  return parts.join(" + ") || `${point.price_pp}pp`
}

function formatCompactNumber(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, "")
}
