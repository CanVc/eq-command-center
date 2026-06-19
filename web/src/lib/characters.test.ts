import { describe, expect, it } from "vitest"

import {
  areaQuantityLabel,
  characterClassLevelLabel,
  equippedItemCount,
  inventoryAreaLabel,
  isStarterOrNoTradeImport,
} from "./characters"

import type { CharacterEquipmentResponse } from "./api"

describe("characters helpers", () => {
  it("formats class and level with safe fallbacks", () => {
    expect(characterClassLevelLabel({ character_class: "Shadow Knight", level: 60 })).toBe(
      "Shadow Knight · Level 60"
    )
    expect(characterClassLevelLabel({ character_class: null, level: null })).toBe(
      "Class unknown · Level unknown"
    )
  })

  it("labels inventory areas for tabs and grouped quantities", () => {
    expect(inventoryAreaLabel("shared_bank")).toBe("Shared Bank")
    expect(
      areaQuantityLabel({
        areas: ["carried", "bank", "shared_bank"],
        area_quantities: { carried: 2, bank: 5, shared_bank: 1 },
      })
    ).toBe("Carried 2 · Bank 5 · Shared Bank 1")
  })

  it("flags starter or no-trade import markers", () => {
    expect(isStarterOrNoTradeImport({ is_starter_item: false, is_no_trade_import: false })).toBe(false)
    expect(isStarterOrNoTradeImport({ is_starter_item: true, is_no_trade_import: false })).toBe(true)
    expect(isStarterOrNoTradeImport({ is_starter_item: false, is_no_trade_import: true })).toBe(true)
  })

  it("counts filled equipment slots", () => {
    const equipment = {
      slots: {
        EAR_1: { item: { name: "Earring" } },
        EAR_2: { item: null },
        PRIMARY: { item: { name: "Sword" } },
      },
    } as unknown as CharacterEquipmentResponse

    expect(equippedItemCount(equipment)).toBe(2)
    expect(equippedItemCount(null)).toBe(0)
  })
})
