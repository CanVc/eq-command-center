import { describe, expect, it, vi } from "vitest"

import {
  DEFAULT_SERVER,
  SERVER_STORAGE_KEY,
  normalizeServer,
  readPreferredServer,
  savePreferredServer,
  type ServerStorage,
} from "./server-preference"

function createStorage(initialValue: string | null = null): ServerStorage {
  let value = initialValue

  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_, nextValue: string) => {
      value = nextValue
    }),
    removeItem: vi.fn(() => {
      value = null
    }),
  }
}

describe("server preference", () => {
  it("normalizes blank or mixed-case server names", () => {
    expect(normalizeServer(" Frostreaver ")).toBe("frostreaver")
    expect(normalizeServer("")).toBe(DEFAULT_SERVER)
    expect(normalizeServer(null)).toBe(DEFAULT_SERVER)
  })

  it("reads the preferred server from storage", () => {
    const storage = createStorage(" Mischief ")

    expect(readPreferredServer(storage)).toBe("mischief")
    expect(storage.getItem).toHaveBeenCalledWith(SERVER_STORAGE_KEY)
  })

  it("saves the normalized server to storage", () => {
    const storage = createStorage()

    expect(savePreferredServer(" Thornblade ", storage)).toBe("thornblade")
    expect(storage.setItem).toHaveBeenCalledWith(SERVER_STORAGE_KEY, "thornblade")
    expect(readPreferredServer(storage)).toBe("thornblade")
  })

  it("falls back to the default server when storage throws", () => {
    const storage: ServerStorage = {
      getItem: vi.fn(() => {
        throw new Error("blocked")
      }),
      setItem: vi.fn(() => {
        throw new Error("blocked")
      }),
      removeItem: vi.fn(),
    }

    expect(readPreferredServer(storage)).toBe(DEFAULT_SERVER)
    expect(savePreferredServer("oakwynd", storage)).toBe("oakwynd")
  })
})
