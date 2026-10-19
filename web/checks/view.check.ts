import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'
import { parseSpec } from '../src/spec'

const path = process.env.DAWRI_VIEW_CONTRACT
if (!path) throw new Error('Run mise run web-contract to generate recorded responses first')
const responses: unknown = JSON.parse(readFileSync(path, 'utf8'))

test.each(['2025/2026', '2026/2027'])('Python %s spec passes the frontend contract', (season) => {
  if (!responses || typeof responses !== 'object' || !(season in responses)) {
    throw new Error(`Missing recorded response: ${season}`)
  }
  const spec = parseSpec(Reflect.get(responses, season))
  expect(spec.root).toBe('page')
  expect(Object.keys(spec.elements)).toHaveLength(4)
})
