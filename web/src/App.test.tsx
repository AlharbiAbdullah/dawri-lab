import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, afterEach, expect, test, vi } from 'vitest'
import App from './App'
import { testSpec } from './test-spec'

const SEASONS = [
  { season: '2025/2026', season_id: 'old', finished: 2, upcoming: 1 },
  { season: '2026/2027', season_id: 'new', finished: 2, upcoming: 1 },
]
const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  fetchMock.mockImplementation(async (input) => {
    const url = String(input)
    if (url === '/api/seasons') return Response.json(SEASONS)
    if (url === '/api/seasons/2025-2026/view') return Response.json(testSpec())
    if (url === '/api/seasons/2026-2027/view') {
      return Response.json(testSpec('2026/2027'))
    }
    throw new Error(`Unexpected fetch: ${url}`)
  })
})

afterEach(() => vi.unstubAllGlobals())

test('renders API data through the real registry without changing numeric props', async () => {
  const spec = testSpec()
  fetchMock.mockResolvedValueOnce(Response.json(SEASONS)).mockResolvedValueOnce(Response.json(spec))
  render(<App />)
  expect(await screen.findByRole('table', { name: 'Standings' })).toBeVisible()
  const table = screen.getByRole('table', { name: 'Team metrics' })
  expect(within(table).getByRole('cell', { name: '1.30' })).toBeVisible()
  expect(spec.elements['metrics']?.props['rows']).toEqual([
    { team_name: 'Team A', points: 3, xg_for: 1.3 },
  ])
  expect(screen.getByRole('combobox', { name: 'Season' })).toHaveValue('2025/2026')
})

test('clears the old page and ignores a slower response after selection changes', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('2025/2026: 2 finished, 1 upcoming')
  let finishOld: (response: Response) => void = () => {
    throw new Error('Not pending')
  }
  const oldRequest = new Promise<Response>((resolve) => {
    finishOld = resolve
  })
  fetchMock.mockReturnValueOnce(oldRequest)
  await user.selectOptions(screen.getByRole('combobox'), '2026/2027')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.getByText('Loading...')).toBeVisible()
  await user.selectOptions(screen.getByRole('combobox'), '2025/2026')
  await screen.findByText('2025/2026: 2 finished, 1 upcoming')
  await act(async () => {
    finishOld(Response.json(testSpec('2026/2027')))
  })
  expect(screen.queryByText('2026/2027: 2 finished, 1 upcoming')).not.toBeInTheDocument()
  expect(screen.getByText('2025/2026: 2 finished, 1 upcoming')).toBeVisible()
})

test('Refresh fetches again, shows request errors, and recovers', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('table', { name: 'Standings' })
  fetchMock.mockRejectedValueOnce(new Error('Offline'))
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load season. Try Refresh.')
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await screen.findByRole('table', { name: 'Standings' })
  expect(fetchMock).toHaveBeenCalledTimes(4)
})

test('recovers when fetching the season list fails', async () => {
  const user = userEvent.setup()
  fetchMock.mockRejectedValueOnce(new Error('Offline'))
  render(<App />)
  await screen.findByRole('alert')
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await screen.findByRole('table', { name: 'Standings' })
})

test.each(['unknown type', 'wrong props', 'dangling child', 'cycle', 'orphan', 'leaf children'])(
  'rejects %s instead of rendering a partial page',
  async (problem) => {
    const spec = testSpec()
    const page = spec.elements['page']
    const summary = spec.elements['summary']
    if (!page || !summary) throw new Error('Broken test fixture')
    if (problem === 'unknown type') summary.type = 'Script'
    if (problem === 'wrong props') summary.props = { content: 12 }
    if (problem === 'dangling child') page.children = ['missing']
    if (problem === 'cycle') page.children = ['page']
    if (problem === 'orphan') page.children = ['summary']
    if (problem === 'leaf children') summary.children = ['standings']
    fetchMock
      .mockResolvedValueOnce(Response.json(SEASONS))
      .mockResolvedValueOnce(Response.json(spec))
    render(<App />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot display this page.')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  },
)

test('keeps both table captions when there are no finished matches', async () => {
  fetchMock
    .mockResolvedValueOnce(Response.json(SEASONS))
    .mockResolvedValueOnce(Response.json(testSpec('2025/2026', false)))
  render(<App />)
  await screen.findByRole('table', { name: 'Standings' })
  expect(screen.getByRole('table', { name: 'Team metrics' })).toBeVisible()
  expect(screen.getAllByText('No finished matches.')).toHaveLength(2)
})

test('treats non-200 responses as request failures', async () => {
  fetchMock
    .mockResolvedValueOnce(Response.json(SEASONS))
    .mockResolvedValueOnce(new Response('', { status: 500 }))
  render(<App />)
  await waitFor(() =>
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load season. Try Refresh.'),
  )
})
