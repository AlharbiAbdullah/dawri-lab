import { defineRegistry } from '@json-render/react'
import { catalog } from './catalog'
import { DataTable } from './DataTable'

export const { registry } = defineRegistry(catalog, {
  components: {
    Page: ({ props, children }) => (
      <main className="page">
        <h1>{props.title}</h1>
        {children}
      </main>
    ),
    Text: ({ props }) => <p className="summary">{props.content}</p>,
    Table: ({ props }) => <DataTable {...props} />,
  },
})
