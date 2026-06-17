import { afterEach, describe, expect, it, vi } from "vitest"

describe("Magelo helpers", () => {
  afterEach(() => {
    vi.resetModules()
    vi.unstubAllGlobals()
  })

  it("reports unavailable when no browser window exists", async () => {
    const { scanMageloItems } = await import("./magelo")

    expect(scanMageloItems()).toBe(false)
  })

  it("scans Magelo items and notifies subscribers when the scanner is available", async () => {
    const scan = vi.fn()
    vi.stubGlobal("window", {
      Magelobar: { scan },
    })

    const { getMageloStatus, scanMageloItems, subscribeMageloStatus } = await import("./magelo")
    const statuses: string[] = []
    const unsubscribe = subscribeMageloStatus((status) => statuses.push(status))

    expect(scanMageloItems()).toBe(true)

    unsubscribe()
    expect(scan).toHaveBeenCalledOnce()
    expect(getMageloStatus()).toBe("loaded")
    expect(statuses).toContain("loaded")
  })

  it("marks Magelo unavailable when the scanner throws", async () => {
    vi.stubGlobal("window", {
      Magelobar: {
        scan: () => {
          throw new Error("Magelo failed")
        },
      },
    })

    const { getMageloStatus, scanMageloItems } = await import("./magelo")

    expect(scanMageloItems()).toBe(false)
    expect(getMageloStatus()).toBe("unavailable")
  })
})
