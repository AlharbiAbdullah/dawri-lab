import type { Spec } from '@json-render/core'
import { parseSpec } from './spec'

export interface CachedPage {
  spec: Spec
  etag: string | null
}

export async function fetchPage(
  url: string,
  signal: AbortSignal,
  pages: Map<string, CachedPage>,
): Promise<Spec> {
  const cached = pages.get(url)
  const headers = new Headers()
  if (cached?.etag) headers.set('If-None-Match', cached.etag)
  const response = await fetch(url, { signal, headers, cache: 'no-store' })
  if (response.status === 304) {
    if (!cached) throw new Error('Received 304 without a validated page')
    return cached.spec
  }
  if (response.status !== 200) throw new Error(`Request failed: ${response.status}`)
  const spec = parseSpec(await response.json())
  signal.throwIfAborted()
  pages.set(url, { spec, etag: response.headers.get('ETag') })
  return spec
}
