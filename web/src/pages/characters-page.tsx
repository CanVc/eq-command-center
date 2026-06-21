import { AlertTriangle, Backpack, Shield, UserRound } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { EquipmentPaperdoll } from "@/components/equipment-paperdoll"
import { ItemLink } from "@/components/item-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  fetchCharacterEquipment,
  fetchCharacterInventory,
  type CharacterEquipmentResponse,
  type CharacterInventoryArea,
  type CharacterInventoryGroup,
  type CharacterInventoryResponse,
  type CharacterSummary,
} from "@/lib/api"
import {
  CHARACTER_INVENTORY_AREAS,
  areaQuantityLabel,
  characterClassLevelLabel,
  inventoryAreaLabel,
  isStarterOrNoTradeImport,
} from "@/lib/characters"
import { formatDateTime, formatNumber, formatPrice } from "@/lib/format"
import { cn } from "@/lib/utils"
import { SellInventoryPage } from "@/pages/sell-inventory-page"

type CharactersPageProps = {
  characters: CharacterSummary[]
  server: string
}

type RemoteState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string }

type CharacterPageView = "inventory" | "sell"

export function CharactersPage({ characters, server }: CharactersPageProps) {
  const [selectedCharacterName, setSelectedCharacterName] = useState<string | null>(
    () => characters[0]?.character_name ?? null
  )
  const [activeView, setActiveView] = useState<CharacterPageView>("inventory")
  const [inventoryArea, setInventoryArea] = useState<CharacterInventoryArea>("all")
  const [detailRefreshKey, setDetailRefreshKey] = useState(0)
  const [equipmentState, setEquipmentState] = useState<RemoteState<CharacterEquipmentResponse>>(
    () => characters.length > 0 ? { status: "loading" } : { status: "idle" }
  )
  const [inventoryState, setInventoryState] = useState<RemoteState<CharacterInventoryResponse>>(
    () => characters.length > 0 ? { status: "loading" } : { status: "idle" }
  )

  const activeCharacterName = useMemo(() => {
    if (characters.length === 0) {
      return null
    }

    if (selectedCharacterName && characters.some((character) => character.character_name === selectedCharacterName)) {
      return selectedCharacterName
    }

    return characters[0].character_name
  }, [characters, selectedCharacterName])

  const selectedCharacter = useMemo(
    () => characters.find((character) => character.character_name === activeCharacterName) ?? null,
    [activeCharacterName, characters]
  )

  useEffect(() => {
    if (!activeCharacterName) {
      return undefined
    }

    let isActive = true

    fetchCharacterEquipment(activeCharacterName)
      .then((equipment) => {
        if (isActive) {
          setEquipmentState({ status: "ready", data: equipment })
        }
      })
      .catch((error) => {
        if (isActive) {
          setEquipmentState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown equipment API error",
          })
        }
      })

    return () => {
      isActive = false
    }
  }, [activeCharacterName, detailRefreshKey])

  useEffect(() => {
    if (!activeCharacterName) {
      return undefined
    }

    let isActive = true

    fetchCharacterInventory(activeCharacterName, inventoryArea)
      .then((inventory) => {
        if (isActive) {
          setInventoryState({ status: "ready", data: inventory })
        }
      })
      .catch((error) => {
        if (isActive) {
          setInventoryState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown inventory API error",
          })
        }
      })

    return () => {
      isActive = false
    }
  }, [activeCharacterName, detailRefreshKey, inventoryArea])

  const selectCharacter = (characterName: string) => {
    if (characterName === activeCharacterName) {
      return
    }

    setEquipmentState({ status: "loading" })
    setInventoryState({ status: "loading" })
    setSelectedCharacterName(characterName)
    setInventoryArea("all")
  }

  const retryDetails = () => {
    if (activeCharacterName) {
      setEquipmentState({ status: "loading" })
      setInventoryState({ status: "loading" })
    }
    setDetailRefreshKey((current) => current + 1)
  }

  const changeInventoryArea = (area: CharacterInventoryArea) => {
    setInventoryState({ status: "loading" })
    setInventoryArea(area)
  }

  if (characters.length === 0) {
    return <NoCharactersState server={server} />
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Character Inventory</h2>
          <p className="text-sm text-muted-foreground">
            Select an imported character to review worn gear and grouped carried, bank, or shared bank items.
          </p>
        </div>
        <Badge variant="outline" className="rounded-md">
          {formatNumber(characters.length)} characters
        </Badge>
      </div>

      <Tabs value={activeView} onValueChange={(value) => setActiveView(value as CharacterPageView)}>
        <TabsList className="flex h-auto w-fit flex-wrap justify-start" aria-label="Character views">
          <TabsTrigger value="inventory">Inventory</TabsTrigger>
          <TabsTrigger value="sell">Sell</TabsTrigger>
        </TabsList>
      </Tabs>

      {activeView === "inventory" ? (
        <div className="grid gap-4 xl:grid-cols-[18rem_minmax(0,1fr)]">
          <div className="grid gap-4 content-start">
            <CharacterRoster
              characters={characters}
              selectedCharacterName={activeCharacterName}
              onSelect={selectCharacter}
            />
            {selectedCharacter ? <CharacterSummaryCard character={selectedCharacter} /> : null}
          </div>

          <div className="grid min-w-0 gap-4">
            {selectedCharacter ? <ImportFreshnessNotice character={selectedCharacter} /> : null}
            <EquipmentSection state={equipmentState} server={server} onRetry={retryDetails} />
            <InventorySection
              state={inventoryState}
              area={inventoryArea}
              server={server}
              onAreaChange={changeInventoryArea}
              onRetry={retryDetails}
            />
          </div>
        </div>
      ) : (
        <SellInventoryPage characters={characters} server={server} />
      )}
    </section>
  )
}

function NoCharactersState({ server }: { server: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserRound aria-hidden="true" className="size-4" />
          <h2>No characters imported</h2>
        </CardTitle>
        <CardDescription>
          No character inventory import is available for {server}. Import an EverQuest inventory dump, then refresh this page.
        </CardDescription>
      </CardHeader>
    </Card>
  )
}

function CharacterRoster({
  characters,
  selectedCharacterName,
  onSelect,
}: {
  characters: CharacterSummary[]
  selectedCharacterName: string | null
  onSelect: (characterName: string) => void
}) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <UserRound aria-hidden="true" className="size-4" />
          <h3>Characters</h3>
        </CardTitle>
        <CardDescription>Imported characters on the active server.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2" role="list" aria-label="Character list">
          {characters.map((character) => {
            const selected = character.character_name === selectedCharacterName

            return (
              <button
                key={character.character_name}
                type="button"
                aria-pressed={selected}
                onClick={() => onSelect(character.character_name)}
                className={cn(
                  "rounded-lg border p-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  selected ? "border-primary bg-primary/10" : "border-border bg-background"
                )}
              >
                <span className="block font-medium">{character.character_name}</span>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {character.server ?? "server unknown"} · {characterClassLevelLabel(character)}
                </span>
                <span className="mt-2 flex flex-wrap gap-1">
                  <Badge variant={character.freshness.imported ? "outline" : "secondary"} className="rounded-md">
                    {character.freshness.imported ? "Imported" : "Not imported"}
                  </Badge>
                  {character.starter_item_count > 0 ? (
                    <Badge variant="secondary" className="rounded-md">
                      {character.starter_item_count} starter/no-trade *
                    </Badge>
                  ) : null}
                </span>
              </button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

function CharacterSummaryCard({ character }: { character: CharacterSummary }) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>
          <h3>{character.character_name}</h3>
        </CardTitle>
        <CardDescription>{characterClassLevelLabel(character)}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-3 text-sm">
          <SummaryRow label="Server" value={character.server ?? "n/a"} />
          <SummaryRow label="Last import" value={formatDateTime(character.last_imported_at)} />
          <SummaryRow label="Equipment" value={formatNumber(character.equipment_item_count)} />
          <SummaryRow label="Inventory rows" value={formatNumber(character.inventory_item_count)} />
          <SummaryRow label="Inventory quantity" value={formatNumber(character.inventory_quantity)} />
          <SummaryRow label="Distinct items" value={formatNumber(character.distinct_item_count)} />
          <SummaryRow label="Unenriched" value={formatNumber(character.unenriched_item_count)} />
          <SummaryRow label="Unpriced" value={formatNumber(character.unpriced_item_count)} />
        </dl>
      </CardContent>
    </Card>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  )
}

function ImportFreshnessNotice({ character }: { character: CharacterSummary }) {
  if (character.freshness.imported) {
    return null
  }

  return (
    <div className="flex items-start gap-3 rounded-xl border border-dashed bg-muted/30 p-4 text-sm text-muted-foreground">
      <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
      <div>
        <p className="font-medium text-foreground">No import found for this character.</p>
        <p>Equipment and inventory sections stay visible but may be empty until an inventory dump is imported.</p>
      </div>
    </div>
  )
}

function EquipmentSection({
  state,
  server,
  onRetry,
}: {
  state: RemoteState<CharacterEquipmentResponse>
  server: string
  onRetry: () => void
}) {
  if (state.status === "idle") {
    return null
  }

  if (state.status === "loading") {
    return <DetailLoading title="Loading equipment" icon="shield" />
  }

  if (state.status === "error") {
    return <DetailError title="Unable to load equipment" message={state.message} onRetry={onRetry} />
  }

  return <EquipmentPaperdoll equipment={state.data} server={server} />
}

function InventorySection({
  state,
  area,
  server,
  onAreaChange,
  onRetry,
}: {
  state: RemoteState<CharacterInventoryResponse>
  area: CharacterInventoryArea
  server: string
  onAreaChange: (area: CharacterInventoryArea) => void
  onRetry: () => void
}) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Backpack aria-hidden="true" className="size-4" />
          <h3>Inventory List</h3>
        </CardTitle>
        <CardDescription>Grouped by item across carried bags, bank, and shared bank.</CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={area} onValueChange={(value) => onAreaChange(value as CharacterInventoryArea)}>
          <TabsList className="mb-4 flex h-auto w-full flex-wrap justify-start">
            {CHARACTER_INVENTORY_AREAS.map((option) => (
              <TabsTrigger key={option} value={option}>
                {inventoryAreaLabel(option)}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>

        {state.status === "idle" ? (
          <EmptyList label="Select a character to load inventory." />
        ) : state.status === "loading" ? (
          <DetailLoading title="Loading inventory" icon="bag" compact />
        ) : state.status === "error" ? (
          <DetailError title="Unable to load inventory" message={state.message} onRetry={onRetry} />
        ) : (
          <InventoryTable inventory={state.data} server={server} />
        )}
      </CardContent>
    </Card>
  )
}

function InventoryTable({ inventory, server }: { inventory: CharacterInventoryResponse; server: string }) {
  if (inventory.items.length === 0) {
    const areaLabel = inventory.area === "all" ? "inventory" : `${inventoryAreaLabel(inventory.area).toLowerCase()} inventory`

    return (
      <EmptyList
        label={`No ${areaLabel} items imported for ${inventory.character_name}.`}
      />
    )
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline" className="rounded-md">
          {formatNumber(inventory.item_count)} grouped items
        </Badge>
        <span>{formatNumber(inventory.total_quantity)} total quantity</span>
        <span>{formatNumber(inventory.location_count)} raw locations</span>
      </div>

      <div className="overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Item</TableHead>
              <TableHead>Qty</TableHead>
              <TableHead>Areas</TableHead>
              <TableHead>Market</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {inventory.items.map((item) => (
              <InventoryRow key={`${item.item_id ?? item.name}-${item.areas.join("-")}`} item={item} server={server} />
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function InventoryRow({ item, server }: { item: CharacterInventoryGroup; server: string }) {
  const itemDetail = item.item
  const specialImport = isStarterOrNoTradeImport(itemDetail)

  return (
    <TableRow className={cn(specialImport && "bg-muted/40 text-muted-foreground")}>
      <TableCell className="min-w-[16rem] whitespace-normal">
        <div className="flex min-w-0 items-start gap-2">
          <InventoryIcon item={itemDetail} />
          <div className="min-w-0">
            <ItemLink
              itemId={itemDetail.item_id}
              name={specialImport ? `${item.name} *` : item.name}
              server={server}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {itemDetail.slot_display ?? itemDetail.item_type ?? "No slot data"}
            </p>
          </div>
        </div>
      </TableCell>
      <TableCell>{formatNumber(item.quantity)}</TableCell>
      <TableCell className="min-w-[12rem] text-xs text-muted-foreground">{areaQuantityLabel(item)}</TableCell>
      <TableCell>
        <div className="grid gap-1">
          <span>{formatPrice(itemDetail.price.market_price_pp)}</span>
          <span className="text-xs text-muted-foreground">{itemDetail.price.market_price_source ?? "no reference"}</span>
        </div>
      </TableCell>
      <TableCell className="min-w-[12rem]">
        <div className="flex flex-wrap gap-1">
          {specialImport ? (
            <Badge variant="secondary" className="rounded-md">
              Starter / No Trade *
            </Badge>
          ) : null}
          {item.is_container ? (
            <Badge variant="outline" className="rounded-md">
              Container
            </Badge>
          ) : null}
          {!item.enriched ? (
            <Badge variant="outline" className="rounded-md text-muted-foreground">
              {item.enrichment_status === "inventory_stub" ? "Inventory stub" : "Not enriched"}
            </Badge>
          ) : null}
          {!item.has_price ? (
            <Badge variant="outline" className="rounded-md text-muted-foreground">
              No price
            </Badge>
          ) : null}
        </div>
      </TableCell>
    </TableRow>
  )
}

function InventoryIcon({
  item,
}: {
  item: Pick<CharacterInventoryGroup["item"], "icon_url" | "icon_id" | "name">
}) {
  if (item.icon_url) {
    return <img src={item.icon_url} alt="" className="size-9 shrink-0 rounded-md border bg-muted object-cover" loading="lazy" />
  }

  return (
    <span
      aria-hidden="true"
      className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-[0.62rem] font-semibold text-muted-foreground"
      title={item.icon_id ? `Icon ${item.icon_id}` : `No icon for ${item.name}`}
    >
      {item.icon_id ? `#${item.icon_id}` : item.name.slice(0, 2).toUpperCase()}
    </span>
  )
}

function DetailLoading({ title, icon, compact = false }: { title: string; icon: "shield" | "bag"; compact?: boolean }) {
  const Icon = icon === "bag" ? Backpack : Shield

  return (
    <div
      role="status"
      aria-label={title}
      className={cn("rounded-xl border bg-card p-4 shadow-sm", compact ? "min-h-24" : "min-h-48")}
    >
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon aria-hidden="true" className="size-4 animate-pulse" />
        {title}…
      </div>
    </div>
  )
}

function DetailError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
      <div className="flex items-start gap-3">
        <AlertTriangle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-destructive" />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-destructive">{title}</p>
          <p className="mt-1 break-words text-muted-foreground">{message}</p>
          <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onRetry}>
            Retry
          </Button>
        </div>
      </div>
    </div>
  )
}

function EmptyList({ label }: { label: string }) {
  return <p className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">{label}</p>
}
