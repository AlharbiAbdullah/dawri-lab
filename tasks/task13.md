# L13: a page described by data (json-render)

## The concept

### The problem

L12 can answer `GET /seasons/2025-2026/metrics` with numbers. A
browser still needs code to decide which number goes into which table,
what its heading says, and whether to print two decimals. `/docs` describes
the API; it does not give a fan a page.

L11's pages made those presentation choices inside each tool. Here we
make the choice once on the server and send it as JSON. The browser
receives both the facts and the instruction to display them, with a
small, known set of components.

### What we want

FastAPI returns a page specification: component names, their properties,
and the order they appear. React supplies the actual components.
json-render connects the two. Select a season and see its match counts,
standings, and points/GD/xG comparison. Every number comes from the
serving layer finished in L12.

A specification is ordinary JSON. It can be built deterministically by
Python and returned by an API. The library supports API responses and
static specifications as sources. [Official spec documentation](https://json-render.dev/docs/specs).

### What you will understand at the end

| Idea | In one line |
|---|---|
| Spec | JSON describing a page, rather than HTML or executable code. |
| Catalog | The allowed component names and the types of their properties. |
| Registry | The React implementation for each catalog component. |
| Renderer | Reads the spec and creates components from the registry. |
| Boundary validation | Checks server JSON before a browser tries to render it. |

### Before and after

```text
BEFORE                                AFTER
API returns rows                      API also returns a page spec
page layout lives in each consumer    server chooses components and order
browser needs to know each endpoint   page comes from one /view response
metric definitions stay in Ossie      metric definitions still stay in Ossie
```

Guardrails for every tier:

- Facts only. No forecasts, generated prose, prompts, model calls or keys.
- The 2026/2027 ingest freeze continues through L13. L14 ends it.
- Use L12's published Parquet generation and shared semantic reader.
  The browser never opens DuckDB or computes a metric. Formatting a
  number to two decimals is presentation, not a metric.
- Keep the existing API routes and their response shapes. A new route
  means an intentional `mise run openapi` snapshot update.
- Same inputs produce the same spec, including element IDs and order.
  No timestamps or random IDs. Never send raw HTML or JavaScript in props.
- Use the real tools: `@json-render/core`, `@json-render/react`, Zod,
  React, TypeScript and Vite. Commit the frontend dependency lockfile
  when the lesson is closed. No dependency installation is needed just
  to read this task.
- Python tests stay offline and leave real `data/` and logs untouched.
  Frontend tests use simulated DOM and mocked fetch. Existing Python
  checks stay green; the Python suite stays under 10 seconds.
- A tier is done when its target output matches. Hard is optional.

---

## Easy: one element, from a blank file

**Target output**

Input, already parsed by L12's model:

```python
SeasonSummary(
    season="2026/2027",
    season_id="3677a75aaa514e43b2840e7fa367c91d",
    finished=2,
    upcoming=1,
)
```

Output, compared as a JSON object:

```json
{
  "root": "summary",
  "elements": {
    "summary": {
      "type": "Text",
      "props": {"content": "2026/2027: 2 finished, 1 upcoming"},
      "children": []
    }
  }
}
```

**Spec**

1. Create `src/dawri/ui.py`. One function, `season_header`, accepts
   a `SeasonSummary` and returns the spec above with the supplied
   season and counts. About ten lines. No database, HTTP or React yet.
2. `tests/test_ui.py`: `test_season_header` checks that exact object.
   A second case with `finished=0`, `upcoming=0` checks that the counts
   come from the input. The supplied object must remain unchanged.
3. In chat: `root` contains the string `summary`, not the Text object.
   What does a renderer have to look up before it can draw anything?

**Withheld:** how to construct the nested Python value. One decision.
The JSON shape is the contract, not a code skeleton.

---

## Mid: the season page

**Target output**

```text
$ uv run dawri serve                    # terminal 1
$ cd web                               # terminal 2
$ npm run dev -- --host 127.0.0.1
Local: http://127.0.0.1:5173/

Page on the frozen real data, 2025/2026 selected:

Dawri
Season [2025/2026 v]                    [Refresh]
2025/2026: 306 finished, 0 upcoming

Standings
Rank  Team       Played  Won  Drawn  Lost  GF  GA  GD  Points
1     Al Nassr   34      28   2      4     91  28  63  86
... all 18 teams, in the API's rank order

Team metrics
Team       Points  GD  xG for  xG against
Al Nassr   86      63  64.38   21.95
... all 18 teams, in the metrics API's order

$ npm test -- --run
all frontend checks pass
$ npm run build
TypeScript check and production build pass
$ uv run pytest
all previous tests plus the new backend checks pass
```

**Spec**

4. Add `GET /seasons/{season}/view`, returning a Pydantic-validated
   spec. Reuse easy's `season_header`; do not replace it. Read the
   summary, standings and metrics through L12's existing readers on
   **one resolved serving generation per request**. Do not make HTTP
   requests from the API to itself or duplicate its SQL/metric logic.
   `api.py` remains under the file limit; extract only code this route
   actually needs to share.
5. The spec has exactly four elements. Root `page`, type `Page`,
   props `{"title":"Dawri"}`, children in this order:
   `summary`, `standings`, `metrics`. `summary` is easy's element,
   unchanged. The two remaining elements have type `Table`, empty
   children, and these properties:

   | Element | title | columns, in order |
   |---|---|---|
   | `standings` | `Standings` | `rank`, `team_name`, `played`, `won`, `drawn`, `lost`, `goals_for`, `goals_against`, `goal_difference`, `points` |
   | `metrics` | `Team metrics` | `team_name`, `points`, `goal_difference`, `xg_for`, `xg_against` |

   Each `columns` entry has `key`, `label`, `format`. See Reference
   for exact labels and formats. `rows` is the matching L12 endpoint's
   JSON rows, in its existing order. Standings use `type=table`.
   Metrics request the four named metrics in the listed order, so
   points descending, then team name, determines their order. Do not
   calculate standings rank from this different order.
6. Unknown season: L12's same 404 body. A configured season with no
   finished matches still returns 200: its summary, both tables with
   empty `rows`, and all column definitions. Keep L12's existing ETag
   behavior on this `/seasons/...` route. Update OpenAPI intentionally.
7. Create `web/` with the Vite React TypeScript template. Keep its
   generated structure; add the catalog and registry in `web/src/`.
   The catalog has exactly `Page`, `Text`, `Table`, with the props
   above. Only `Page` accepts children. Use the library's catalog,
   registry and `Renderer`, rather than writing a component switch.
   Validate fetched specs against the catalog and check tree structure
   before rendering. Unknown types, wrong prop types or dangling IDs
   show `Cannot display this page.` instead of a partial page.
8. The application shell owns the season select and Refresh button.
   Fetch `/seasons` for options in config order; start with the first.
   Fetch that season's `/view` on selection or Refresh. Use Vite's
   `/api` development proxy to `http://127.0.0.1:8000`, stripping `/api`
   before forwarding. Requests from browser code use `/api/...`.
   Bind Vite to loopback, port 5173, strict port, no automatic opening.
9. During a fetch show `Loading...`. Remove the previous season's
   page immediately on a selection change. Only the most recently
   requested page may appear, even if older responses arrive later.
   Fetch failure shows `Could not load season. Try Refresh.`; controls
   stay usable. A Table renders semantic HTML with its title as a
   caption, column headers, and `No finished matches.` for zero rows.
   Numeric cells align right; xG uses exactly two decimals. At 390 px
   the tables scroll within their container, not the whole document.
10. Verification, with exact cases rather than a fixed total count:

    ```text
    Backend, recorded fixtures, reuse L12's one-build test setup:
      view structure       four elements, exact links/columns/titles
      view facts           counts 2/1; 4 standings and 4 metric rows;
                           every value equals its L12 endpoint
      empty season         2025/2026 counts 0/0; both row arrays empty
      unknown season       2024-2025: L12's same 404

    Frontend, Vitest + Testing Library, mocked fetch:
      render               real registry/Renderer, both tables present,
                           1.3 renders as 1.30; numeric JSON preserved
      switch               old page clears; latest selection wins when
                           responses arrive in reverse order
      refresh/error        Refresh fetches again; rejected request shows
                           the error; another Refresh recovers
      invalid spec         unsupported type, wrong props, dangling child
                           each shows the display error
      empty rows           both captions and both empty messages appear
    ```

    Add `mise run web-check`: frontend tests and TypeScript/build.
    CI installs locked frontend dependencies with `npm ci` and runs it.
    Manual check: both real seasons, 390 px width, and repeated Refresh
    during `dawri load` then `dawri build`. No locks or failed responses;
    do not run ingest. Do not claim a visual check from unit tests alone.
11. In chat: trace one displayed xG cell back through the spec, the
    API and Ossie to the published facts. Which part chooses its value,
    which part chooses its position, and which part prints two decimals?

**Withheld:** how to reuse existing readers with one connection and
merge easy's spec. Catalog/registry implementation, request state,
stale-response handling, and tests that exercise the real renderer.

---

## Hard (optional): prove the shared contract and conditional refresh

**Target output**

```text
First view request                     200 + ETag + body
Refresh with that ETag, same facts      304 + ETag, no body; page stays
Refresh after changed publication       200 + new ETag; new page appears
Switch to another season               that season's own request/cache
Unknown component from Python          frontend contract check fails
```

**Spec**

12. Add an offline contract check that sends actual `/view` responses
    from L12's recorded fixture setup through the frontend catalog and
    tree validators. Cover both configured seasons. Generate the test
    input during the check, not from real `data/` and not by manually
    copying a sample response. CI runs this check. Prove it catches a
    temporary Python component rename (`Table` to `LeagueTable`) while
    the Pydantic models still accept the response, then restore it.
13. Refresh sends `If-None-Match` after a successful request. Keep a
    spec and ETag per season for this browser session. A 304 has no
    JSON to parse: keep the corresponding validated page. A 200
    validates and replaces both. A failed/invalid response never becomes
    cached content. A previously selected season may use its cached
    page only after the server confirms it or returns a replacement.
14. Test 200 -> 304 retention, 200 -> changed 200 replacement, two
    seasons with different cache entries, and failed-request recovery.
    Reuse L12's temporary publish test pattern to prove changed facts
    change the `/view` ETag. Real `data/` stays untouched by the tests.
15. In chat: an ETag can save response bytes. Why does the current
    server still run database queries on every Refresh?

**Withheld:** connecting the Python and TypeScript test boundaries;
cache state and conditional-response handling. No new caching package
is required by the spec; use one if it helps meet the behavior.

---

## Reference

### The wire shape

`root` names an entry in `elements`. Every element has `type`, `props`
and `children`; children are element IDs. All four elements must be
reachable exactly once from `page`; no cycles or missing references.
This lesson uses plain props, not state expressions or actions.

`Table.props` is `title: string`, `columns: Column[]`, `rows: Row[]`.
A Column is `key: string`, `label: string`, `format` one of
`text`, `integer`, `decimal`. A Row maps keys to strings or numbers.
Backend row types retain L12's stricter standings/metric types.

| key | label | format |
|---|---|---|
| `rank` | Rank | integer |
| `team_name` | Team | text |
| `played` | Played | integer |
| `won` | Won | integer |
| `drawn` | Drawn | integer |
| `lost` | Lost | integer |
| `goals_for` | GF | integer |
| `goals_against` | GA | integer |
| `goal_difference` | GD | integer |
| `points` | Points | integer |
| `xg_for` | xG for | decimal |
| `xg_against` | xG against | decimal |

The recorded 2026/2027 fixtures have two finished matches, one upcoming,
and four teams. NEOM SC has 3 points and `xg_for=1.3`. The recorded
2025/2026 season has no matches. Do not substitute the real season's
306 matches in an offline test.

L12's tied rank limitation remains: `row_number()` assigns different
positions even when every sporting criterion ties. This lesson displays
the existing API ranks. L14 owns the shared-position brief requirement.

### Sources and starting points

- [json-render specs](https://json-render.dev/docs/specs): root, elements,
  API/static sources and structural validation.
- [Catalog](https://json-render.dev/docs/catalog) and
  [core API](https://json-render.dev/docs/api/core): `defineCatalog`,
  React schema, Zod props and catalog validation. Current components
  declare child slots with `slots`; check the installed version's API.
- [Registry](https://json-render.dev/docs/registry): `defineRegistry`
  maps catalog entries to React implementations.
- [React quick start](https://json-render.dev/docs/quick-start): Renderer
  and its providers. Use the static spec path for this lesson.
- [Vite](https://vite.dev/guide/) and its
  [development proxy](https://vite.dev/config/server-options.html#server-proxy).

`src/dawri/api.py`, `src/dawri/semantic.py`, `tests/test_api.py` and
`docs/openapi.json` are the completed L12 starting point. `task14.md`
is the actuator, a separate lesson.
