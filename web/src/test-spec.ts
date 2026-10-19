import type { Spec } from '@json-render/core'

export function testSpec(season = '2025/2026', hasRows = true): Spec {
  const rows = hasRows ? [{ team_name: 'Team A', points: 3, xg_for: 1.3 }] : []
  return {
    root: 'page',
    elements: {
      page: {
        type: 'Page',
        props: { title: 'Dawri' },
        children: ['summary', 'standings', 'metrics'],
      },
      summary: {
        type: 'Text',
        props: { content: `${season}: 2 finished, 1 upcoming` },
        children: [],
      },
      standings: {
        type: 'Table',
        props: {
          title: 'Standings',
          columns: [
            { key: 'team_name', label: 'Team', format: 'text' },
            { key: 'points', label: 'Points', format: 'integer' },
          ],
          rows,
        },
        children: [],
      },
      metrics: {
        type: 'Table',
        props: {
          title: 'Team metrics',
          columns: [
            { key: 'team_name', label: 'Team', format: 'text' },
            { key: 'xg_for', label: 'xG for', format: 'decimal' },
          ],
          rows,
        },
        children: [],
      },
    },
  }
}
