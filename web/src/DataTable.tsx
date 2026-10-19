import type { InferComponentProps } from '@json-render/core'
import type { JSX } from 'react'
import type { catalog } from './catalog'

type TableProps = InferComponentProps<typeof catalog, 'Table'>

function formatCell(
  value: string | number | undefined,
  format: string,
): string | number | undefined {
  return format === 'decimal' && typeof value === 'number' ? value.toFixed(2) : value
}

export function DataTable({ title, columns, rows }: TableProps): JSX.Element {
  return (
    <div className="table-scroll" role="region" aria-label={title} tabIndex={0}>
      <table>
        <caption>{title}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={column.format === 'text' ? '' : 'numeric'}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="empty">
                No finished matches.
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr key={String(row['team_name'] ?? index)}>
                {columns.map((column) => (
                  <td key={column.key} className={column.format === 'text' ? '' : 'numeric'}>
                    {formatCell(row[column.key], column.format)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
