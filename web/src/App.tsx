import { Renderer, JSONUIProvider } from '@json-render/react'
import type { JSX } from 'react'
import { registry } from './registry'
import { useSeasonPage } from './use-season-page'
import './App.css'

export default function App(): JSX.Element {
  const { seasons, season, view, selectSeason, refreshPage } = useSeasonPage()
  return (
    <div className="app-shell">
      <header className="toolbar">
        <p className="eyebrow">SAUDI PRO LEAGUE / SEASON EXPLORER</p>
        <div className="controls">
          <label htmlFor="season">Season</label>
          <select
            id="season"
            value={season}
            onChange={(event) => selectSeason(event.target.value)}
            disabled={seasons.length === 0}
          >
            {seasons.map((option) => (
              <option key={option.season} value={option.season}>
                {option.season}
              </option>
            ))}
          </select>
          <button type="button" onClick={refreshPage}>
            Refresh
          </button>
        </div>
      </header>
      {view.status === 'loading' && <p role="status">Loading...</p>}
      {view.status === 'error' && <p role="alert">{view.message}</p>}
      {view.status === 'ready' && (
        <JSONUIProvider registry={registry}>
          <Renderer spec={view.spec} registry={registry} />
        </JSONUIProvider>
      )}
    </div>
  )
}
