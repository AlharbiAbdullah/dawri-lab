import { z } from 'zod'

export const seasonsSchema = z.array(
  z.object({
    season: z.string(),
    season_id: z.string(),
    finished: z.number().int(),
    upcoming: z.number().int(),
  }),
)
export type Season = z.infer<typeof seasonsSchema>[number]

export async function fetchJson(url: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { signal, cache: 'no-store' })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}
