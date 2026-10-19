import { validateSpec, type Spec } from '@json-render/core'
import { catalog } from './catalog'
import { z } from 'zod'

const wireSchema = z
  .object({
    root: z.string(),
    elements: z.record(
      z.string(),
      z
        .object({
          type: z.string(),
          props: z.record(z.string(), z.unknown()),
          children: z.array(z.string()),
        })
        .strict(),
    ),
  })
  .strict()

export class InvalidSpecError extends Error {}

function isTree(spec: Spec): boolean {
  const seen = new Set<string>()
  function visit(id: string): boolean {
    const element = spec.elements[id]
    if (!element || seen.has(id)) return false
    seen.add(id)
    const children = element.children ?? []
    if (element.type !== 'Page' && children.length > 0) return false
    return children.every(visit)
  }
  return visit(spec.root) && seen.size === Object.keys(spec.elements).length
}

export function parseSpec(raw: unknown): Spec {
  const result = wireSchema.safeParse(raw)
  if (!catalog.validate(raw).success || !result.success)
    throw new InvalidSpecError('Invalid component props')
  const spec: Spec = result.data
  // 0.21's multi-component catalog treats props as unknown; check the chosen schema.
  const components: Record<string, { props: z.ZodType }> = catalog.data.components
  for (const element of Object.values(spec.elements)) {
    if (!components[element.type]?.props.safeParse(element.props).success) {
      throw new InvalidSpecError('Invalid component props')
    }
  }
  if (!validateSpec(spec, { checkOrphans: true }).valid || !isTree(spec)) {
    throw new InvalidSpecError('Invalid component tree')
  }
  return spec
}
