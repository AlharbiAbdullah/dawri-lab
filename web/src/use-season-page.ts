import { useEffect, useRef, useState } from 'react'
import type { Spec } from '@json-render/core'
import { fetchJson, seasonsSchema, type Season } from './client'
import { InvalidSpecError } from './spec'
import { fetchPage, type CachedPage } from './page-cache'
const DISPLAY_ERROR = 'Cannot display this page.'
const REQUEST_ERROR = 'Could not load season. Try Refresh.'
type View =
  { status: 'loading' } | { status: 'ready'; spec: Spec } | { status: 'error'; message: string }
interface SeasonPage {
  seasons: Season[]
  season: string
  view: View
  selectSeason: (value: string) => void
  refreshPage: () => void
}
export function useSeasonPage(): SeasonPage {
  const pages = useRef(new Map<string, CachedPage>())
  const [seasons, setSeasons] = useState<Season[]>([])
  const [season, setSeason] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [view, setView] = useState<View>({ status: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    let isCurrent = true
    async function load(): Promise<void> {
      try {
        if (seasons.length === 0) {
          const options = seasonsSchema.parse(await fetchJson('/api/seasons', controller.signal))
          if (!isCurrent) return
          const first = options[0]
          if (!first) throw new Error('No seasons available')
          setSeasons(options)
          setSeason(first.season)
          return
        }
        const spec = await fetchPage(
          `/api/seasons/${encodeURIComponent(season.replaceAll('/', '-'))}/view`,
          controller.signal,
          pages.current,
        )
        if (isCurrent) setView({ status: 'ready', spec })
      } catch (error) {
        if (!isCurrent) return
        setView({
          status: 'error',
          message: error instanceof InvalidSpecError ? DISPLAY_ERROR : REQUEST_ERROR,
        })
      }
    }
    void load()
    return () => {
      isCurrent = false
      controller.abort()
    }
  }, [season, seasons, refresh])
  function selectSeason(value: string): void {
    setView({ status: 'loading' })
    setSeason(value)
  }
  function refreshPage(): void {
    setView({ status: 'loading' })
    setRefresh((value) => value + 1)
  }
  return { seasons, season, view, selectSeason, refreshPage }
}
