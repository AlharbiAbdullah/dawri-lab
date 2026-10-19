import { defineCatalog } from '@json-render/core'
import { schema } from '@json-render/react/schema'
import { z } from 'zod'

export const catalog = defineCatalog(schema, {
  components: {
    Page: {
      props: z.object({ title: z.string() }).strict(),
      slots: ['default'],
    },
    Text: { props: z.object({ content: z.string() }).strict() },
    Table: {
      props: z
        .object({
          title: z.string(),
          columns: z.array(
            z
              .object({
                key: z.string(),
                label: z.string(),
                format: z.enum(['text', 'integer', 'decimal']),
              })
              .strict(),
          ),
          rows: z.array(z.record(z.string(), z.union([z.string(), z.number()]))),
        })
        .strict(),
    },
  },
  actions: {},
})
