import { describe, expect, it, vi } from "vitest"

import { fetchHealth } from "./api"

describe("fetchHealth", () => {
  it("calls the health endpoint through the Vite proxy path", async () => {
    const payload = { status: "ok", db_path: "C:/tmp/eqmarket.sqlite" }
    const fetcher = vi.fn(async () => {
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    })

    await expect(fetchHealth(fetcher)).resolves.toEqual(payload)

    expect(fetcher).toHaveBeenCalledWith("/api/health", {
      headers: {
        Accept: "application/json",
      },
    })
  })

  it("raises an ApiError when the health endpoint is unavailable", async () => {
    const fetcher = vi.fn(async () => new Response("offline", { status: 503 }))

    await expect(fetchHealth(fetcher)).rejects.toEqual(
      expect.objectContaining({
        name: "ApiError",
        status: 503,
        message: "GET /api/health failed with 503",
      })
    )
  })
})
