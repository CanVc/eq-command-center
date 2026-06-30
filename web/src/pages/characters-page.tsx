import { AlertTriangle, ArrowDown, ArrowUp, Backpack, Plus, RotateCcw, Shield, Swords, Trash2, UserRound } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

import { EquipmentPaperdoll } from "@/components/equipment-paperdoll"
import { ItemIcon } from "@/components/item-icon"
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
  fetchCharacterUpgrades,
  type CharacterEquipmentResponse,
  type CharacterInventoryArea,
  type CharacterInventoryGroup,
  type CharacterInventoryResponse,
  type CharacterSummary,
  type CharacterUpgradeCandidate,
  type CharacterUpgradeStat,
  type CharacterUpgradeSourceFilter,
  type CharacterUpgradesResponse,
} from "@/lib/api"
import {
  CHARACTER_INVENTORY_AREAS,
  CHARACTER_UPGRADE_STATS,
  CHARACTER_UPGRADE_SLOTS,
  areaQuantityLabel,
  characterClassLevelLabel,
  inventoryAreaLabel,
  isStarterOrNoTradeImport,
  upgradeStatLabel,
  upgradeSlotLabel,
  upgradeSourceFilterLabel,
  upgradeSourceLabel,
} from "@/lib/characters"
import { formatDateTime, formatNumber, formatPrice } from "@/lib/format"
import { primaryItemSourceLabel } from "@/lib/item-detail"
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

type CharacterPageView = "inventory" | "upgrades" | "sell"

type UpgradeFilters = {
  slot: string
  source: CharacterUpgradeSourceFilter
  stats: CharacterUpgradeStat[]
  betterOnly: boolean
  maxPriceInput: string
}

const DEFAULT_UPGRADE_FILTERS: UpgradeFilters = {
  slot: "all",
  source: "all",
  stats: ["ac", "hp"],
  betterOnly: true,
  maxPriceInput: "",
}

const inputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function CharactersPage({ characters, server }: CharactersPageProps) {
  const [selectedCharacterName, setSelectedCharacterName] = useState<string | null>(
    () => characters[0]?.character_name ?? null
  )
  const [activeView, setActiveView] = useState<CharacterPageView>("inventory")
  const [inventoryArea, setInventoryArea] = useState<CharacterInventoryArea>("all")
  const [upgradeFilters, setUpgradeFilters] = useState<UpgradeFilters>(DEFAULT_UPGRADE_FILTERS)
  const [detailRefreshKey, setDetailRefreshKey] = useState(0)
  const [equipmentState, setEquipmentState] = useState<RemoteState<CharacterEquipmentResponse>>(
    () => characters.length > 0 ? { status: "loading" } : { status: "idle" }
  )
  const [inventoryState, setInventoryState] = useState<RemoteState<CharacterInventoryResponse>>(
    () => characters.length > 0 ? { status: "loading" } : { status: "idle" }
  )
  const [upgradesState, setUpgradesState] = useState<RemoteState<CharacterUpgradesResponse>>({ status: "idle" })

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

  useEffect(() => {
    if (!activeCharacterName || activeView !== "upgrades") {
      return undefined
    }

    let isActive = true

    fetchCharacterUpgrades(activeCharacterName, {
      slot: upgradeFilters.slot === "all" ? null : upgradeFilters.slot,
      source: upgradeFilters.source,
      stats: upgradeFilters.stats,
      betterOnly: upgradeFilters.betterOnly,
      maxPricePp: upgradeMaxPrice(upgradeFilters.maxPriceInput),
      limit: 50,
    })
      .then((upgrades) => {
        if (isActive) {
          setUpgradesState({ status: "ready", data: upgrades })
        }
      })
      .catch((error) => {
        if (isActive) {
          setUpgradesState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown upgrades API error",
          })
        }
      })

    return () => {
      isActive = false
    }
  }, [activeCharacterName, activeView, detailRefreshKey, upgradeFilters])

  const changeActiveView = (view: CharacterPageView) => {
    if (view === "upgrades" && activeCharacterName) {
      setUpgradesState({ status: "loading" })
    }
    setActiveView(view)
  }

  const selectCharacter = (characterName: string) => {
    if (characterName === activeCharacterName) {
      return
    }

    setEquipmentState({ status: "loading" })
    setInventoryState({ status: "loading" })
    if (activeView === "upgrades") {
      setUpgradesState({ status: "loading" })
    }
    setSelectedCharacterName(characterName)
    setInventoryArea("all")
  }

  const retryDetails = () => {
    if (activeCharacterName) {
      setEquipmentState({ status: "loading" })
      setInventoryState({ status: "loading" })
      if (activeView === "upgrades") {
        setUpgradesState({ status: "loading" })
      }
    }
    setDetailRefreshKey((current) => current + 1)
  }

  const changeInventoryArea = (area: CharacterInventoryArea) => {
    setInventoryState({ status: "loading" })
    setInventoryArea(area)
  }

  const changeUpgradeFilter = <K extends keyof UpgradeFilters>(key: K, value: UpgradeFilters[K]) => {
    setUpgradesState({ status: "loading" })
    setUpgradeFilters((current) => ({ ...current, [key]: value }))
  }

  const resetUpgradeFilters = () => {
    setUpgradesState({ status: "loading" })
    setUpgradeFilters(DEFAULT_UPGRADE_FILTERS)
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

      <Tabs value={activeView} onValueChange={(value) => changeActiveView(value as CharacterPageView)}>
        <TabsList className="flex h-auto w-fit flex-wrap justify-start" aria-label="Character views">
          <TabsTrigger value="inventory">Inventory</TabsTrigger>
          <TabsTrigger value="upgrades">Upgrades</TabsTrigger>
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
      ) : activeView === "upgrades" ? (
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
            <UpgradesSection
              state={upgradesState}
              filters={upgradeFilters}
              server={server}
              onFilterChange={changeUpgradeFilter}
              onResetFilters={resetUpgradeFilters}
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

function UpgradesSection({
  state,
  filters,
  server,
  onFilterChange,
  onResetFilters,
  onRetry,
}: {
  state: RemoteState<CharacterUpgradesResponse>
  filters: UpgradeFilters
  server: string
  onFilterChange: <K extends keyof UpgradeFilters>(key: K, value: UpgradeFilters[K]) => void
  onResetFilters: () => void
  onRetry: () => void
}) {
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="flex items-center gap-2">
          <Swords aria-hidden="true" className="size-4" />
          <h3>Gear Upgrades</h3>
        </CardTitle>
        <CardDescription>Character-specific upgrades from owned inventory, local listings, and market prices.</CardDescription>
      </CardHeader>
      <CardContent>
        <UpgradeFiltersForm filters={filters} onFilterChange={onFilterChange} onReset={onResetFilters} />

        {state.status === "idle" ? (
          <EmptyList label="Select a character to load upgrade candidates." />
        ) : state.status === "loading" ? (
          <DetailLoading title="Loading upgrades" icon="sword" compact />
        ) : state.status === "error" ? (
          <DetailError title="Unable to load upgrades" message={state.message} onRetry={onRetry} />
        ) : (
          <UpgradeCandidatesTable upgrades={state.data} server={server} />
        )}
      </CardContent>
    </Card>
  )
}

function UpgradeFiltersForm({
  filters,
  onFilterChange,
  onReset,
}: {
  filters: UpgradeFilters
  onFilterChange: <K extends keyof UpgradeFilters>(key: K, value: UpgradeFilters[K]) => void
  onReset: () => void
}) {
  const updateStat = (index: number, stat: CharacterUpgradeStat) => {
    const nextStats = filters.stats.map((currentStat, currentIndex) => currentIndex === index ? stat : currentStat)
    onFilterChange("stats", nextStats)
  }

  const addStat = () => {
    const nextStat = CHARACTER_UPGRADE_STATS.find((stat) => !filters.stats.includes(stat)) ?? "ac"
    onFilterChange("stats", [...filters.stats, nextStat])
  }

  const moveStat = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction
    if (targetIndex < 0 || targetIndex >= filters.stats.length) {
      return
    }

    const nextStats = [...filters.stats]
    const currentStat = nextStats[index]
    nextStats[index] = nextStats[targetIndex]
    nextStats[targetIndex] = currentStat
    onFilterChange("stats", nextStats)
  }

  const removeStat = (index: number) => {
    if (filters.stats.length <= 1) {
      return
    }

    onFilterChange("stats", filters.stats.filter((_, currentIndex) => currentIndex !== index))
  }

  return (
    <form
      aria-label="Upgrade filters"
      className="mb-4 grid gap-3"
      onSubmit={(event) => event.preventDefault()}
    >
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[repeat(3,minmax(0,1fr))_auto]">
        <label className="grid gap-1.5 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Slot</span>
          <select
            aria-label="Upgrade slot filter"
            className={inputClassName}
            value={filters.slot}
            onChange={(event) => onFilterChange("slot", event.target.value)}
          >
            {CHARACTER_UPGRADE_SLOTS.map((slot) => (
              <option key={slot} value={slot}>
                {upgradeSlotLabel(slot)}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1.5 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Source</span>
          <select
            aria-label="Upgrade source filter"
            className={inputClassName}
            value={filters.source}
            onChange={(event) => onFilterChange("source", event.target.value as CharacterUpgradeSourceFilter)}
          >
            {(["all", "owned", "market"] as CharacterUpgradeSourceFilter[]).map((source) => (
              <option key={source} value={source}>
                {upgradeSourceFilterLabel(source)}
              </option>
            ))}
          </select>
        </label>

        <label className="grid gap-1.5 text-sm">
          <span className="text-xs font-medium text-muted-foreground">Max cost</span>
          <input
            aria-label="Upgrade max cost filter"
            className={inputClassName}
            inputMode="numeric"
            value={filters.maxPriceInput}
            placeholder="Any"
            onChange={(event) => onFilterChange("maxPriceInput", event.target.value)}
          />
        </label>

        <div className="flex items-end">
          <Button type="button" variant="outline" className="w-full xl:w-auto" onClick={onReset}>
            <RotateCcw aria-hidden="true" />
            Reset
          </Button>
        </div>
      </div>

      <div className="grid gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <label className="flex min-h-8 items-center gap-2 text-sm">
            <input
              aria-label="Show only better stats"
              type="checkbox"
              className="size-4 rounded border-input accent-primary"
              checked={filters.betterOnly}
              onChange={(event) => onFilterChange("betterOnly", event.target.checked)}
            />
            <span>Show only better stats</span>
          </label>
          <Button type="button" variant="outline" size="sm" onClick={addStat}>
            <Plus aria-hidden="true" />
            Add stat
          </Button>
        </div>

        <div className="grid gap-2">
          {filters.stats.map((stat, index) => (
            <div key={`${stat}-${index}`} className="grid gap-2 sm:grid-cols-[2rem_minmax(0,1fr)_auto] sm:items-center">
              <Badge variant="outline" className="flex h-9 items-center justify-center rounded-md">
                {index + 1}
              </Badge>
              <select
                aria-label={`Upgrade stat ${index + 1}`}
                className={inputClassName}
                value={stat}
                onChange={(event) => updateStat(index, event.target.value as CharacterUpgradeStat)}
              >
                {CHARACTER_UPGRADE_STATS.map((option) => (
                  <option key={option} value={option} disabled={filters.stats.includes(option) && option !== stat}>
                    {upgradeStatLabel(option)}
                  </option>
                ))}
              </select>
              <div className="flex gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  title="Move stat up"
                  aria-label={`Move ${upgradeStatLabel(stat)} up`}
                  disabled={index === 0}
                  onClick={() => moveStat(index, -1)}
                >
                  <ArrowUp aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  title="Move stat down"
                  aria-label={`Move ${upgradeStatLabel(stat)} down`}
                  disabled={index === filters.stats.length - 1}
                  onClick={() => moveStat(index, 1)}
                >
                  <ArrowDown aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  title="Remove stat"
                  aria-label={`Remove ${upgradeStatLabel(stat)}`}
                  disabled={filters.stats.length <= 1}
                  onClick={() => removeStat(index)}
                >
                  <Trash2 aria-hidden="true" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </form>
  )
}

function UpgradeCandidatesTable({ upgrades, server }: { upgrades: CharacterUpgradesResponse; server: string }) {
  if (upgrades.candidates.length === 0) {
    return <EmptyList label={`No upgrade candidates found for ${upgrades.character_name}.`} />
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge variant="outline" className="rounded-md">
          {formatNumber(upgrades.candidate_count)} candidates
        </Badge>
        <span>Stats {upgrades.stats.map(upgradeStatLabel).join(" > ")}</span>
        <span>{upgrades.better_only ? "Only better stats" : "Tradeoffs allowed"}</span>
        <span>Source {upgradeSourceFilterLabel(upgrades.source)}</span>
        <span>Budget {formatPrice(upgrades.max_price_pp)}</span>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Slot</TableHead>
              <TableHead>Candidate</TableHead>
              <TableHead>Current</TableHead>
              <TableHead>Deltas</TableHead>
              <TableHead>Cost</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {upgrades.candidates.map((candidate) => (
              <UpgradeCandidateRow
                key={upgradeCandidateKey(candidate)}
                candidate={candidate}
                selectedStats={upgrades.stats}
                server={server}
              />
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function UpgradeCandidateRow({
  candidate,
  selectedStats,
  server,
}: {
  candidate: CharacterUpgradeCandidate
  selectedStats: CharacterUpgradeStat[]
  server: string
}) {
  const dropSourceLabel = primaryItemSourceLabel(candidate.candidate.sources)
  const details = [
    { label: "Slot", value: candidate.slot_label },
    { label: "Cost", value: formatPrice(candidate.cost_pp) },
    { label: "Drop", value: dropSourceLabel },
  ]

  return (
    <TableRow>
      <TableCell className="whitespace-nowrap">
        <Badge variant="outline" className="rounded-md">
          {candidate.slot_label}
        </Badge>
      </TableCell>
      <TableCell className="min-w-[18rem] whitespace-normal">
        <div className="flex min-w-0 items-start gap-2">
          <ItemIcon
            iconUrl={candidate.candidate.icon_url}
            iconId={candidate.candidate.icon_id}
            itemId={candidate.candidate.item_id}
            name={candidate.candidate.name}
          />
          <div className="min-w-0">
            <ItemLink itemId={candidate.candidate.item_id} name={candidate.candidate.name} server={server} details={details} />
            <p className="mt-1 text-xs text-muted-foreground">
              {candidate.candidate.slot_display ?? candidate.candidate.item_type ?? "No slot data"}
            </p>
            {dropSourceLabel ? (
              <p className="mt-1 text-xs text-muted-foreground">Drop {dropSourceLabel}</p>
            ) : null}
          </div>
        </div>
      </TableCell>
      <TableCell className="min-w-[12rem] whitespace-normal text-sm">
        {candidate.current_item ? (
          <ItemLink itemId={candidate.current_item.item_id} name={candidate.current_item.name} server={server} />
        ) : (
          <span className="text-muted-foreground">Empty slot</span>
        )}
      </TableCell>
      <TableCell className="min-w-[18rem]">
        <UpgradeDeltaList candidate={candidate} selectedStats={selectedStats} />
      </TableCell>
      <TableCell className="whitespace-nowrap">
        <div className="grid gap-1">
          <span>{formatPrice(candidate.cost_pp)}</span>
          <span className="text-xs text-muted-foreground">Market {formatPrice(candidate.market_price_pp)}</span>
        </div>
      </TableCell>
      <TableCell className="min-w-[10rem]">
        <div className="flex flex-wrap gap-1">
          <Badge variant="outline" className="rounded-md">
            {upgradeSourceLabel(candidate.source)}
          </Badge>
          {candidate.decision_status ? (
            <Badge variant="secondary" className="rounded-md">
              {candidate.decision_status}
            </Badge>
          ) : null}
          {candidate.source === "owned" && candidate.areas.length > 0 ? (
            <span className="basis-full text-xs text-muted-foreground">{areaQuantityLabel(candidate)}</span>
          ) : null}
          {candidate.listing ? (
            <span className="basis-full text-xs text-muted-foreground">
              {candidate.listing.seller ?? "unknown seller"} · {candidate.listing.price_raw ?? formatPrice(candidate.listing.price_pp)}
            </span>
          ) : null}
        </div>
      </TableCell>
    </TableRow>
  )
}

function UpgradeDeltaList({
  candidate,
  selectedStats,
}: {
  candidate: CharacterUpgradeCandidate
  selectedStats: CharacterUpgradeStat[]
}) {
  const deltaStats = orderedDeltaStats(selectedStats)

  return (
    <div className="flex flex-wrap gap-1">
      {deltaStats.map((stat) => (
        <Badge key={stat} variant="outline" className={cn("rounded-md", deltaBadgeClassName(candidate.deltas[stat]))}>
          {upgradeStatLabel(stat)} {formatSignedDelta(candidate.deltas[stat])}
        </Badge>
      ))}
    </div>
  )
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
          <ItemIcon iconUrl={itemDetail.icon_url} iconId={itemDetail.icon_id} itemId={itemDetail.item_id} name={itemDetail.name} />
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

function DetailLoading({ title, icon, compact = false }: { title: string; icon: "shield" | "bag" | "sword"; compact?: boolean }) {
  const Icon = icon === "bag" ? Backpack : icon === "sword" ? Swords : Shield

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

function upgradeMaxPrice(value: string): number | null {
  const normalized = value.trim()
  if (!normalized) {
    return null
  }

  const parsed = Number(normalized)
  if (!Number.isFinite(parsed) || parsed < 0) {
    return null
  }

  return Math.round(parsed)
}

function upgradeCandidateKey(candidate: CharacterUpgradeCandidate): string {
  return `${candidate.slot_key}:${candidate.source}:${candidate.candidate.item_id}:${candidate.listing?.listing_id ?? "market"}`
}

function orderedDeltaStats(selectedStats: CharacterUpgradeStat[]): CharacterUpgradeStat[] {
  const contextStats: CharacterUpgradeStat[] = ["ac", "hp", "mana", "resists_total", "ratio"]
  const stats: CharacterUpgradeStat[] = []

  for (const stat of [...selectedStats, ...contextStats]) {
    if (!stats.includes(stat)) {
      stats.push(stat)
    }
  }

  return stats
}

function formatSignedDelta(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "n/a"
  }

  if (Math.abs(value) < 1 && value !== 0) {
    return `${value > 0 ? "+" : ""}${value.toFixed(3)}`
  }

  return `${value > 0 ? "+" : ""}${formatNumber(value)}`
}

function deltaBadgeClassName(value: number | null): string {
  if (value === null || value === 0) {
    return "text-muted-foreground"
  }

  return value > 0
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
    : "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300"
}
