# Dawri web

L13's React page consumes the deterministic component spec from L12's API.
Requires Node 26. Dependencies are locked in `package-lock.json`.

```bash
# Repo root, terminal 1
uv run dawri serve

# web/, terminal 2
npm ci
npm run dev
```

The page is at `http://127.0.0.1:5173`. Vite forwards `/api/...` to
`http://127.0.0.1:8000/...`. It never opens a browser automatically.
If port 8000 is occupied, run `dawri serve --port 8001` and start Vite with
`DAWRI_API_TARGET=http://127.0.0.1:8001 npm run dev`.

The page fetches `/seasons`, then `/seasons/<selected-season>/view`.
Python supplies one Page, one Text and two Tables. `src/catalog.ts` defines
their prop schemas. `src/spec.ts` validates props and tree links.
`src/registry.tsx` maps those names to React components; `DataTable.tsx`
formats decimal cells. `App.tsx` owns selection, loading, errors and Refresh.
Requests cancelled by a newer selection cannot replace the current page.

`src/page-cache.ts` keeps a validated spec and ETag per page URL in memory.
Refresh sends `If-None-Match`. A 304 reuses the matching spec without
parsing a body; a valid 200 replaces the spec and ETag. Failed responses
preserve the last good entry. Switching seasons waits for server confirmation.

From the repo root, `mise run web-check` runs mocked-fetch tests,
TypeScript, production build, lint and formatting checks. The development
proxy belongs to Vite; hosting the built files is outside this lesson.

`mise run web-contract` builds the recorded fixture database, exports actual
FastAPI responses for both seasons to a temporary file, and passes them through
the frontend validators. It runs offline in CI and reads no real `data/`.
