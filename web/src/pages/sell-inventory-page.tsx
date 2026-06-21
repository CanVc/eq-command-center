import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { ArrowUpDown, Check, DollarSign, EyeOff, RotateCcw, Save } from "lucide-react"

import { ItemLink } from "@/components/item-link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  clearCharacterInventoryItemDecision,
  clearGlobalInventoryItemDecision,
  fetchCharacterInventorySellCandidates,
  fetchInventorySellCandidates,
  updateCharacterInventoryItemDecision,
  updateGlobalInventoryItemDecision,
  type CharacterSummary,
  type InventorySellCandidate,
  type InventorySellCandidatesResponse,
  type InventorySellCandidateCategory,
  type InventorySellDecisionScope,
  type InventorySellDecisionStatus,
} from "@/lib/api"
import { CHARACTER_INVENTORY_AREAS, areaQuantityLabel, inventoryAreaLabel } from "@/lib/characters"
import { formatNumber, formatPrice } from "@/lib/format"
import { cn } from "@/lib/utils"

type SellInventoryPageProps = {
  characters: CharacterSummary[]
  server: string
}

type RemoteState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; message: string }

type CharacterFilter = "all" | string
type ZoneFilter = "all" | Exclude<(typeof CHARACTER_INVENTORY_AREAS)[number], "all">
type StatusFilter = "sellable" | "all" | "manual_sell" | "keep" | "ignored" | "unpriced" | "no_drop" | "excluded" | "undecided"
type PriceFilter = "all" | "priced" | "unpriced"
type NoDropFilter = "hide" | "all" | "only"
type SellSortBy = "item" | "quantity" | "character" | "zone" | "unit_price" | "total" | "confidence" | "price_source" | "status"
type SortDirection = "asc" | "desc"

type SellFilters = {
  character: CharacterFilter
  zone: ZoneFilter
  status: StatusFilter
  price: PriceFilter
  noDrop: NoDropFilter
}

type SellSort = {
  by: SellSortBy
  direction: SortDirection
}

const DEFAULT_FILTERS: SellFilters = {
  character: "all",
  zone: "all",
  status: "sellable",
  price: "all",
  noDrop: "hide",
}

const DEFAULT_SORT: SellSort = {
  by: "total",
  direction: "desc",
}

const defaultSortDirectionByColumn: Record<SellSortBy, SortDirection> = {
  item: "asc",
  quantity: "desc",
  character: "asc",
  zone: "asc",
  unit_price: "desc",
  total: "desc",
  confidence: "desc",
  price_source: "asc",
  status: "asc",
}

const statusFilterOptions: Array<{ value: StatusFilter; label: string }> = [
  { value: "sellable", label: "Sellable" },
  { value: "all", label: "All statuses" },
  { value: "manual_sell", label: "Manual sell" },
  { value: "keep", label: "Keep" },
  { value: "ignored", label: "Ignored" },
  { value: "unpriced", label: "No price" },
  { value: "no_drop", label: "No-drop" },
  { value: "excluded", label: "Excluded" },
  { value: "undecided", label: "Undecided" },
]

const inputClassName =
  "h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function SellInventoryPage({ characters, server }: SellInventoryPageProps) {
  const [filters, setFilters] = useState<SellFilters>(DEFAULT_FILTERS)
  const [sort, setSort] = useState<SellSort>(DEFAULT_SORT)
  const [refreshKey, setRefreshKey] = useState(0)
  const [state, setState] = useState<RemoteState<InventorySellCandidatesResponse>>({ status: "loading" })
  const [mutatingKey, setMutatingKey] = useState<string | null>(null)

  const effectiveFilters = useMemo(
    () => isValidCharacterFilter(filters.character, characters) ? filters : { ...filters, character: "all" },
    [characters, filters]
  )

  useEffect(() => {
    let isActive = true

    const request =
      effectiveFilters.character === "all"
        ? fetchInventorySellCandidates(server)
        : fetchCharacterInventorySellCandidates(effectiveFilters.character)

    request
      .then((data) => {
        if (isActive) {
          setState({ status: "ready", data })
        }
      })
      .catch((error) => {
        if (isActive) {
          setState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown sell inventory API error",
          })
        }
      })

    return () => {
      isActive = false
    }
  }, [effectiveFilters.character, refreshKey, server])

  const visibleItems = useMemo(() => {
    if (state.status !== "ready") {
      return []
    }

    return sortSellCandidates(
      state.data.items.filter((item) => matchesFilters(item, effectiveFilters)),
      sort
    )
  }, [effectiveFilters, sort, state])

  const changeFilter = <K extends keyof SellFilters>(key: K, value: SellFilters[K]) => {
    if (key === "character") {
      setState({ status: "loading" })
    }

    setFilters((current) => ({ ...current, [key]: value }))
  }

  const resetFilters = () => {
    if (effectiveFilters.character !== DEFAULT_FILTERS.character) {
      setState({ status: "loading" })
    }

    setFilters(DEFAULT_FILTERS)
  }

  const changeSort = (sortBy: SellSortBy) => {
    setSort((current) => {
      if (current.by === sortBy) {
        return { ...current, direction: current.direction === "asc" ? "desc" : "asc" }
      }

      return { by: sortBy, direction: defaultSortDirectionByColumn[sortBy] }
    })
  }

  const updateDecision = async (
    item: InventorySellCandidate,
    status: InventorySellDecisionStatus,
    notes: string | null
  ) => {
    const itemKey = sellCandidateKey(item)
    const scope = scopeForDecisionUpdate(item, filters.character)
    setMutatingKey(itemKey)

    try {
      if (scope === "character") {
        await updateCharacterInventoryItemDecision(item.character_name, item.item_id, status, notes)
      } else {
        await updateGlobalInventoryItemDecision(item.item_id, server, status, notes)
      }
      setState({ status: "loading" })
      setRefreshKey((current) => current + 1)
    } catch (error) {
      setState({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to update inventory decision",
      })
    } finally {
      setMutatingKey(null)
    }
  }

  const clearDecision = async (item: InventorySellCandidate) => {
    const itemKey = sellCandidateKey(item)
    const scope = scopeForDecisionClear(item, filters.character)
    setMutatingKey(itemKey)

    try {
      if (scope === "character") {
        await clearCharacterInventoryItemDecision(item.character_name, item.item_id)
      } else {
        await clearGlobalInventoryItemDecision(item.item_id, server)
      }
      setState({ status: "loading" })
      setRefreshKey((current) => current + 1)
    } catch (error) {
      setState({
        status: "error",
        message: error instanceof Error ? error.message : "Unable to clear inventory decision",
      })
    } finally {
      setMutatingKey(null)
    }
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Sell Inventory</h2>
          <p className="text-sm text-muted-foreground">
            Review sellable inventory value, manual decisions, and pricing gaps across imported characters.
          </p>
        </div>
        <Badge variant="outline" className="rounded-md">
          {state.status === "ready" ? `${formatNumber(visibleItems.length)} visible` : "Loading"}
        </Badge>
      </div>

      {state.status === "ready" ? <SellSummary response={state.data} /> : null}

      <SellFiltersForm
        characters={characters}
        filters={effectiveFilters}
        onFilterChange={changeFilter}
        onReset={resetFilters}
      />

      {state.status === "loading" ? (
        <PanelState label="Loading sell candidates..." />
      ) : state.status === "error" ? (
        <PanelState
          label={state.message}
          error
          onRetry={() => {
            setState({ status: "loading" })
            setRefreshKey((current) => current + 1)
          }}
        />
      ) : visibleItems.length > 0 ? (
        <SellCandidatesTable
          items={visibleItems}
          server={server}
          sort={sort}
          mutatingKey={mutatingKey}
          characterFilter={effectiveFilters.character}
          onSortChange={changeSort}
          onDecisionChange={(item, status, notes) => void updateDecision(item, status, notes)}
          onDecisionClear={(item) => void clearDecision(item)}
        />
      ) : (
        <PanelState label="No inventory items match the active sell filters." />
      )}
    </section>
  )
}

function SellSummary({ response }: { response: InventorySellCandidatesResponse }) {
  const totalEstimatedValue = response.items.reduce(
    (total, item) => total + (item.estimated_total_pp ?? 0),
    0
  )
  const itemsWithoutPrice = response.items.filter((item) => item.estimated_unit_price_pp === null).length
  const excludedItems = response.categories.excluded.length + response.categories.no_drop.length

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricCard
        label="Total estimated"
        value={formatPrice(totalEstimatedValue)}
        detail={`${formatNumber(response.item_count)} inventory groups`}
      />
      <MetricCard
        label="Sellable value"
        value={formatPrice(response.sellable_total_value_pp)}
        detail={`${formatNumber(response.categories.sellable.length)} sellable groups`}
      />
      <MetricCard
        label="Without price"
        value={formatNumber(itemsWithoutPrice)}
        detail={`${formatNumber(response.categories.unpriced.length)} unpriced candidates`}
      />
      <MetricCard
        label="Excluded"
        value={formatNumber(excludedItems)}
        detail={`${formatNumber(response.categories.no_drop.length)} no-drop, ${formatNumber(response.categories.excluded.length)} default`}
      />
    </div>
  )
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg border bg-card p-3 shadow-sm">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  )
}

function SellFiltersForm({
  characters,
  filters,
  onFilterChange,
  onReset,
}: {
  characters: CharacterSummary[]
  filters: SellFilters
  onFilterChange: <K extends keyof SellFilters>(key: K, value: SellFilters[K]) => void
  onReset: () => void
}) {
  return (
    <form
      aria-label="Sell inventory filters"
      className="grid gap-3 rounded-lg border bg-card p-3 md:grid-cols-2 xl:grid-cols-[repeat(5,minmax(0,1fr))_auto]"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Character</span>
        <select
          aria-label="Sell character filter"
          className={inputClassName}
          value={filters.character}
          onChange={(event) => onFilterChange("character", event.target.value)}
        >
          <option value="all">All characters</option>
          {characters.map((character) => (
            <option key={character.character_name} value={character.character_name}>
              {character.character_name}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Zone</span>
        <select
          aria-label="Sell zone filter"
          className={inputClassName}
          value={filters.zone}
          onChange={(event) => onFilterChange("zone", event.target.value as ZoneFilter)}
        >
          {CHARACTER_INVENTORY_AREAS.map((area) => (
            <option key={area} value={area}>
              {inventoryAreaLabel(area)}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Status</span>
        <select
          aria-label="Sell status filter"
          className={inputClassName}
          value={filters.status}
          onChange={(event) => onFilterChange("status", event.target.value as StatusFilter)}
        >
          {statusFilterOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">Price</span>
        <select
          aria-label="Sell price filter"
          className={inputClassName}
          value={filters.price}
          onChange={(event) => onFilterChange("price", event.target.value as PriceFilter)}
        >
          <option value="all">With or without price</option>
          <option value="priced">With price</option>
          <option value="unpriced">Without price</option>
        </select>
      </label>

      <label className="grid gap-1.5 text-sm">
        <span className="text-xs font-medium text-muted-foreground">No-drop</span>
        <select
          aria-label="Sell no-drop filter"
          className={inputClassName}
          value={filters.noDrop}
          onChange={(event) => onFilterChange("noDrop", event.target.value as NoDropFilter)}
        >
          <option value="hide">Hide no-drop</option>
          <option value="all">Include no-drop</option>
          <option value="only">No-drop only</option>
        </select>
      </label>

      <div className="flex items-end">
        <Button type="button" variant="outline" className="w-full xl:w-auto" onClick={onReset}>
          <RotateCcw aria-hidden="true" />
          Reset
        </Button>
      </div>
    </form>
  )
}

function SellCandidatesTable({
  items,
  server,
  sort,
  mutatingKey,
  characterFilter,
  onSortChange,
  onDecisionChange,
  onDecisionClear,
}: {
  items: InventorySellCandidate[]
  server: string
  sort: SellSort
  mutatingKey: string | null
  characterFilter: CharacterFilter
  onSortChange: (sortBy: SellSortBy) => void
  onDecisionChange: (item: InventorySellCandidate, status: InventorySellDecisionStatus, notes: string | null) => void
  onDecisionClear: (item: InventorySellCandidate) => void
}) {
  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <SortableTableHead sort={sort} sortBy="item" onSortChange={onSortChange}>Item</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="quantity" onSortChange={onSortChange}>Qty</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="character" onSortChange={onSortChange}>Character</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="zone" onSortChange={onSortChange}>Zone</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="unit_price" onSortChange={onSortChange}>Unit price</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="total" onSortChange={onSortChange}>Total value</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="confidence" onSortChange={onSortChange}>Confidence</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="price_source" onSortChange={onSortChange}>Source</SortableTableHead>
            <SortableTableHead sort={sort} sortBy="status" onSortChange={onSortChange}>Status</SortableTableHead>
            <TableHead>Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={sellCandidateKey(item)} className={cn(item.category !== "sellable" && "bg-muted/30")}>
              <TableCell className="min-w-[16rem] whitespace-normal">
                <div className="flex min-w-0 items-start gap-2">
                  <SellItemIcon item={item} />
                  <div className="min-w-0">
                    <ItemLink
                      itemId={item.item_id}
                      name={item.item_name}
                      server={server}
                      details={[
                        { label: "Quantity", value: formatNumber(item.quantity) },
                        { label: "Value", value: formatPrice(item.estimated_total_pp) },
                        { label: "Source", value: formatPriceSource(item) },
                      ]}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      {item.item_type ?? "inventory"}{item.flags ? ` | ${item.flags}` : ""}
                    </p>
                  </div>
                </div>
              </TableCell>
              <TableCell>{formatNumber(item.quantity)}</TableCell>
              <TableCell>{item.character_name}</TableCell>
              <TableCell className="min-w-[10rem] text-xs text-muted-foreground">{areaQuantityLabel(item)}</TableCell>
              <TableCell>{formatPrice(item.estimated_unit_price_pp)}</TableCell>
              <TableCell>{formatPrice(item.estimated_total_pp)}</TableCell>
              <TableCell>{formatConfidence(item.confidence)}</TableCell>
              <TableCell>
                <Badge variant="outline" className="rounded-md">
                  {formatPriceSource(item)}
                </Badge>
              </TableCell>
              <TableCell className="min-w-[10rem]">
                <SellStatusBadge item={item} />
              </TableCell>
              <TableCell className="min-w-[19rem]">
                <SellDecisionActions
                  key={`${sellCandidateKey(item)}:${item.decision?.scope ?? "none"}:${item.decision_status ?? "none"}:${item.decision?.notes ?? ""}`}
                  item={item}
                  disabled={mutatingKey === sellCandidateKey(item)}
                  setScope={scopeForDecisionUpdate(item, characterFilter)}
                  onDecisionChange={onDecisionChange}
                  onDecisionClear={onDecisionClear}
                />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function SortableTableHead({
  sort,
  sortBy,
  onSortChange,
  children,
}: {
  sort: SellSort
  sortBy: SellSortBy
  onSortChange: (sortBy: SellSortBy) => void
  children: ReactNode
}) {
  const active = sort.by === sortBy

  return (
    <TableHead aria-sort={active ? sortDirectionToAria(sort.direction) : undefined}>
      <button
        type="button"
        className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        onClick={() => onSortChange(sortBy)}
      >
        <span>{children}</span>
        <ArrowUpDown aria-hidden="true" className={cn("size-3", active ? "text-foreground" : "text-muted-foreground")} />
        {active ? (
          <span aria-hidden="true" className="text-[0.65rem] uppercase text-muted-foreground">
            {sort.direction}
          </span>
        ) : null}
      </button>
    </TableHead>
  )
}

function SellItemIcon({ item }: { item: InventorySellCandidate }) {
  return (
    <span
      aria-hidden="true"
      className="flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted text-[0.62rem] font-semibold text-muted-foreground"
      title={item.icon_id ? `Icon ${item.icon_id}` : `No icon for ${item.item_name}`}
    >
      {item.icon_id ? `#${item.icon_id}` : item.item_name.slice(0, 2).toUpperCase()}
    </span>
  )
}

function SellStatusBadge({ item }: { item: InventorySellCandidate }) {
  const statusLabel = item.decision_status
    ? `${formatDecisionStatus(item.decision_status)} ${item.decision?.scope ?? "manual"}`
    : formatCategoryLabel(item.category)

  return (
    <div className="grid gap-1">
      <Badge variant="outline" className={cn("rounded-md", statusBadgeClassName(item))}>
        {statusLabel}
      </Badge>
      {item.decision?.notes ? (
        <p className="max-w-[12rem] whitespace-normal text-xs text-muted-foreground">{item.decision.notes}</p>
      ) : item.default_exclusion_reasons.length > 0 ? (
        <p className="max-w-[12rem] whitespace-normal text-xs text-muted-foreground">
          {item.default_exclusion_reasons.map(formatExclusionReason).join(", ")}
        </p>
      ) : null}
    </div>
  )
}

function SellDecisionActions({
  item,
  disabled,
  setScope,
  onDecisionChange,
  onDecisionClear,
}: {
  item: InventorySellCandidate
  disabled: boolean
  setScope: InventorySellDecisionScope
  onDecisionChange: (item: InventorySellCandidate, status: InventorySellDecisionStatus, notes: string | null) => void
  onDecisionClear: (item: InventorySellCandidate) => void
}) {
  const [note, setNote] = useState(item.decision?.notes ?? "")
  const activeStatus = item.decision_status
  const savedNote = item.decision?.notes ?? ""
  const noteChanged = note !== savedNote

  const saveDecision = (status: InventorySellDecisionStatus) => {
    onDecisionChange(item, status, note.trim() || null)
  }

  return (
    <div className="grid gap-2">
      <div className="flex flex-wrap gap-1">
        <DecisionButton
          label="Keep"
          title={`Set ${setScope} keep decision`}
          active={activeStatus === "keep"}
          disabled={disabled}
          tone="keep"
          onClick={() => saveDecision("keep")}
        >
          <Check aria-hidden="true" />
        </DecisionButton>
        <DecisionButton
          label="Sell"
          title={`Set ${setScope} sell decision`}
          active={activeStatus === "sell"}
          disabled={disabled}
          tone="sell"
          onClick={() => saveDecision("sell")}
        >
          <DollarSign aria-hidden="true" />
        </DecisionButton>
        <DecisionButton
          label="Ignore"
          title={`Set ${setScope} ignore decision`}
          active={activeStatus === "ignore"}
          disabled={disabled}
          tone="ignore"
          onClick={() => saveDecision("ignore")}
        >
          <EyeOff aria-hidden="true" />
        </DecisionButton>
        {item.decision ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            title={`Clear ${item.decision.scope} decision`}
            disabled={disabled}
            onClick={() => onDecisionClear(item)}
          >
            <RotateCcw aria-hidden="true" />
            Clear
          </Button>
        ) : null}
      </div>
      <div className="flex min-w-[18rem] gap-2">
        <input
          aria-label={`Decision note for ${item.item_name} on ${item.character_name}`}
          className={inputClassName}
          value={note}
          placeholder="Decision note"
          onChange={(event) => setNote(event.target.value)}
        />
        <Button
          type="button"
          variant="outline"
          size="lg"
          title="Save decision note"
          disabled={disabled || activeStatus === null || !noteChanged}
          onClick={() => {
            if (activeStatus) {
              saveDecision(activeStatus)
            }
          }}
        >
          <Save aria-hidden="true" />
          Save
        </Button>
      </div>
    </div>
  )
}

function DecisionButton({
  label,
  title,
  active,
  disabled,
  tone,
  children,
  onClick,
}: {
  label: string
  title: string
  active: boolean
  disabled: boolean
  tone: "keep" | "sell" | "ignore"
  children: ReactNode
  onClick: () => void
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      title={title}
      aria-pressed={active}
      disabled={disabled}
      className={cn(active && decisionButtonClassName(tone))}
      onClick={onClick}
    >
      {children}
      {label}
    </Button>
  )
}

function PanelState({ label, error = false, onRetry }: { label: string; error?: boolean; onRetry?: () => void }) {
  return (
    <div
      className={cn(
        "rounded-md border border-dashed p-4 text-sm text-muted-foreground",
        error && "border-destructive/40 bg-destructive/5 text-destructive"
      )}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span>{label}</span>
        {onRetry ? (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            <RotateCcw aria-hidden="true" />
            Retry
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function matchesFilters(item: InventorySellCandidate, filters: SellFilters): boolean {
  if (filters.zone !== "all" && !item.areas.includes(filters.zone)) {
    return false
  }

  if (!matchesStatusFilter(item, filters.status)) {
    return false
  }

  if (filters.price === "priced" && item.estimated_unit_price_pp === null) {
    return false
  }

  if (filters.price === "unpriced" && item.estimated_unit_price_pp !== null) {
    return false
  }

  if (filters.status !== "no_drop") {
    if (filters.noDrop === "hide" && item.is_no_drop) {
      return false
    }
    if (filters.noDrop === "only" && !item.is_no_drop) {
      return false
    }
  }

  return true
}

function isValidCharacterFilter(characterFilter: CharacterFilter, characters: CharacterSummary[]): boolean {
  return characterFilter === "all" || characters.some((character) => character.character_name === characterFilter)
}

function matchesStatusFilter(item: InventorySellCandidate, status: StatusFilter): boolean {
  switch (status) {
    case "all":
      return true
    case "sellable":
      return item.category === "sellable"
    case "manual_sell":
      return item.decision_status === "sell"
    case "keep":
      return item.category === "keep"
    case "ignored":
      return item.category === "ignored"
    case "unpriced":
      return item.category === "unpriced"
    case "no_drop":
      return item.category === "no_drop"
    case "excluded":
      return item.category === "excluded"
    case "undecided":
      return item.decision_status === null && item.category === "sellable"
  }
}

function sortSellCandidates(items: InventorySellCandidate[], sort: SellSort): InventorySellCandidate[] {
  return [...items].sort((a, b) => {
    const result = compareSellCandidates(a, b, sort)
    if (result !== 0) {
      return result
    }

    return compareStrings(a.item_name, b.item_name, "asc")
  })
}

function compareSellCandidates(a: InventorySellCandidate, b: InventorySellCandidate, sort: SellSort): number {
  switch (sort.by) {
    case "item":
      return compareStrings(a.item_name, b.item_name, sort.direction)
    case "quantity":
      return compareNumbers(a.quantity, b.quantity, sort.direction)
    case "character":
      return compareStrings(a.character_name, b.character_name, sort.direction)
    case "zone":
      return compareStrings(areaQuantityLabel(a), areaQuantityLabel(b), sort.direction)
    case "unit_price":
      return compareNullableNumbers(a.estimated_unit_price_pp, b.estimated_unit_price_pp, sort.direction)
    case "total":
      return compareNullableNumbers(a.estimated_total_pp, b.estimated_total_pp, sort.direction)
    case "confidence":
      return compareNumbers(confidenceRank(a.confidence), confidenceRank(b.confidence), sort.direction)
    case "price_source":
      return compareStrings(formatPriceSource(a), formatPriceSource(b), sort.direction)
    case "status":
      return compareStrings(formatStatusSortValue(a), formatStatusSortValue(b), sort.direction)
  }
}

function compareStrings(a: string, b: string, direction: SortDirection): number {
  const result = a.localeCompare(b, undefined, { sensitivity: "base" })
  return direction === "asc" ? result : -result
}

function compareNumbers(a: number, b: number, direction: SortDirection): number {
  const result = a - b
  return direction === "asc" ? result : -result
}

function compareNullableNumbers(a: number | null, b: number | null, direction: SortDirection): number {
  if (a === null && b === null) {
    return 0
  }
  if (a === null) {
    return 1
  }
  if (b === null) {
    return -1
  }

  return compareNumbers(a, b, direction)
}

function confidenceRank(confidence: string | null): number {
  switch (confidence?.toLowerCase()) {
    case "manual":
      return 5
    case "high":
      return 4
    case "medium":
      return 3
    case "low":
      return 2
    case "unknown":
      return 1
    case "none":
      return 0
    default:
      return -1
  }
}

function sellCandidateKey(item: InventorySellCandidate): string {
  return `${item.server}:${item.character_name}:${item.item_id}`
}

function scopeForDecisionUpdate(
  item: InventorySellCandidate,
  characterFilter: CharacterFilter
): InventorySellDecisionScope {
  if (characterFilter !== "all") {
    return "character"
  }

  return item.decision?.scope === "character" ? "character" : "global"
}

function scopeForDecisionClear(
  item: InventorySellCandidate,
  characterFilter: CharacterFilter
): InventorySellDecisionScope {
  return item.decision?.scope ?? scopeForDecisionUpdate(item, characterFilter)
}

function sortDirectionToAria(direction: SortDirection): "ascending" | "descending" {
  return direction === "asc" ? "ascending" : "descending"
}

function formatPriceSource(item: Pick<InventorySellCandidate, "price_source" | "price_source_detail">): string {
  switch (item.price_source) {
    case "manual_override":
      return item.price_source_detail === "manual_override_krono" ? "Manual krono" : "Manual"
    case "recent_local_listings":
      return "Recent listings"
    case "market_prices":
      return item.price_source_detail ?? "Market"
    case null:
      return "No price"
    default:
      return item.price_source
  }
}

function formatConfidence(confidence: string | null): string {
  return confidence ? titleCase(confidence) : "n/a"
}

function formatCategoryLabel(category: InventorySellCandidateCategory): string {
  switch (category) {
    case "sellable":
      return "Candidate"
    case "keep":
      return "Keep"
    case "ignored":
      return "Ignored"
    case "no_drop":
      return "No-drop"
    case "unpriced":
      return "No price"
    case "excluded":
      return "Excluded"
  }
}

function formatDecisionStatus(status: InventorySellDecisionStatus): string {
  switch (status) {
    case "keep":
      return "Keep"
    case "sell":
      return "Sell"
    case "ignore":
      return "Ignore"
  }
}

function formatStatusSortValue(item: InventorySellCandidate): string {
  return item.decision_status ? `${item.decision_status}:${item.decision?.scope ?? ""}` : item.category
}

function formatExclusionReason(reason: string): string {
  switch (reason) {
    case "starter":
      return "starter"
    case "no_trade_import":
      return "no-trade import"
    case "container":
      return "container"
    case "consumable":
      return "consumable"
    default:
      return reason
  }
}

function statusBadgeClassName(item: InventorySellCandidate): string {
  const status = item.decision_status ?? item.category

  switch (status) {
    case "sell":
    case "sellable":
      return "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
    case "keep":
      return "border-sky-500/40 bg-sky-500/10 text-sky-700 dark:text-sky-300"
    case "ignore":
    case "ignored":
      return "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-300"
    case "unpriced":
      return "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300"
    case "no_drop":
    case "excluded":
      return "border-muted-foreground/30 bg-muted text-muted-foreground"
  }
}

function decisionButtonClassName(tone: "keep" | "sell" | "ignore"): string {
  switch (tone) {
    case "keep":
      return "border-sky-500/50 bg-sky-500/10 text-sky-700 hover:bg-sky-500/15 dark:text-sky-300"
    case "sell":
      return "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 hover:bg-emerald-500/15 dark:text-emerald-300"
    case "ignore":
      return "border-red-500/50 bg-red-500/10 text-red-700 hover:bg-red-500/15 dark:text-red-300"
  }
}

function titleCase(value: string): string {
  return value.slice(0, 1).toUpperCase() + value.slice(1).toLowerCase()
}
