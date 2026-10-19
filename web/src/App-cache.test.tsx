import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import { testSpec } from './test-spec'

const fetchMock = vi.fn<typeof fetch>()
const SEASONS = [
  { season: '2025/2026', season_id: 'old', finished: 2, upcoming: 1 },
  { season: '2026/2027', season_id: 'new', finished: 2, upcoming: 1 },
]

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockReset()
  fetchMock
    .mockResolvedValueOnce(Response.json(SEASONS))
    .mockResolvedValueOnce(Response.json(testSpec(), { headers: { ETag: '"old"' } }))
})
afterEach(() => vi.unstubAllGlobals())

function lastCondition(): string | null {
  const options = fetchMock.mock.calls.at(-1)?.[1]
  return new Headers(options?.headers).get('If-None-Match')
}

test('Refresh sends its ETag and keeps the validated page on a bodyless 304', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('2025/2026: 2 finished, 1 upcoming')
  const response = new Response(null, { status: 304, headers: { ETag: '"old"' } })
  const parse = vi.spyOn(response, 'json')
  fetchMock.mockResolvedValueOnce(response)
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await screen.findByRole('table', { name: 'Standings' })
  expect(lastCondition()).toBe('"old"')
  expect(parse).not.toHaveBeenCalled()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('a changed 200 replaces the spec and ETag used by the next Refresh', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('table', { name: 'Standings' })
  const changed = testSpec()
  const summary = changed.elements['summary']
  if (!summary) throw new Error('Broken fixture')
  summary.props = { content: '2025/2026: 3 finished, 0 upcoming' }
  fetchMock.mockResolvedValueOnce(Response.json(changed, { headers: { ETag: '"new"' } }))
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await screen.findByText('2025/2026: 3 finished, 0 upcoming')
  expect(lastCondition()).toBe('"old"')
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 304 }))
  await user.click(screen.getByRole('button', { name: 'Refresh' }))
  await screen.findByText('2025/2026: 3 finished, 0 upcoming')
  expect(lastCondition()).toBe('"new"')
})

test('seasons have separate cache entries and wait for confirmation when revisited', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('table', { name: 'Standings' })
  fetchMock.mockResolvedValueOnce(
    Response.json(testSpec('2026/2027'), {
      headers: { ETag: '"other-season"' },
    }),
  )
  await user.selectOptions(screen.getByRole('combobox'), '2026/2027')
  await screen.findByText('2026/2027: 2 finished, 1 upcoming')
  expect(lastCondition()).toBeNull()
  let confirm: (response: Response) => void = () => {
    throw new Error('Not pending')
  }
  fetchMock.mockReturnValueOnce(
    new Promise<Response>((resolve) => {
      confirm = resolve
    }),
  )
  await user.selectOptions(screen.getByRole('combobox'), '2025/2026')
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
  expect(screen.getByText('Loading...')).toBeVisible()
  expect(lastCondition()).toBe('"old"')
  await act(async () => {
    confirm(new Response(null, { status: 304 }))
  })
  await screen.findByText('2025/2026: 2 finished, 1 upcoming')
  fetchMock.mockResolvedValueOnce(new Response(null, { status: 304 }))
  await user.selectOptions(screen.getByRole('combobox'), '2026/2027')
  await screen.findByText('2026/2027: 2 finished, 1 upcoming')
  expect(lastCondition()).toBe('"other-season"')
})

test.each(['network', 'invalid', 'http'])(
  '%s failure does not replace the last good cache entry',
  async (problem) => {
    const user = userEvent.setup()
    render(<App />)
    await screen.findByRole('table', { name: 'Standings' })
    if (problem === 'network') fetchMock.mockRejectedValueOnce(new Error('Offline'))
    if (problem === 'invalid') {
      fetchMock.mockResolvedValueOnce(
        Response.json(
          { root: 'missing', elements: {} },
          {
            headers: { ETag: '"invalid"' },
          },
        ),
      )
    }
    if (problem === 'http') fetchMock.mockResolvedValueOnce(new Response(null, { status: 500 }))
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    await screen.findByRole('alert')
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 304 }))
    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    await screen.findByText('2025/2026: 2 finished, 1 upcoming')
    expect(lastCondition()).toBe('"old"')
  },
)
