export type HealthResponse = {
  status: string
  db_path: string
}

export type Fetcher = (
  input: RequestInfo | URL,
  init?: RequestInit
) => Promise<Response>

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "")
const HEALTH_PATH = "/api/health"

export async function fetchHealth(fetcher: Fetcher = fetch): Promise<HealthResponse> {
  const response = await fetcher(`${API_BASE_URL}${HEALTH_PATH}`, {
    headers: {
      Accept: "application/json",
    },
  })

  if (!response.ok) {
    throw new ApiError(response.status, `GET ${HEALTH_PATH} failed with ${response.status}`)
  }

  return (await response.json()) as HealthResponse
}
