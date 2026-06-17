import type { ItemDetail, ItemListing } from "@/lib/api"

export type PriceHistoryPoint = {
  listingId: number
  timestamp: string
  price_pp: number
  price_raw: string | null
  seller: string | null
}

export type ExternalItemLink = {
  label: string
  href: string
}

export function buildPriceHistory(listings: ItemListing[]): PriceHistoryPoint[] {
  return listings
    .filter((listing) => listing.price_pp !== null)
    .map((listing) => ({
      listingId: listing.listing_id,
      timestamp: listing.timestamp,
      price_pp: listing.price_pp as number,
      price_raw: listing.price_raw,
      seller: listing.seller,
    }))
    .sort((left, right) => {
      const timestampDelta = timestampValue(left.timestamp) - timestampValue(right.timestamp)
      return timestampDelta === 0 ? left.listingId - right.listingId : timestampDelta
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
