# L11b: a report built from Ossie (Evidence)

Lesson 11 has three paths over the same Ossie document: 11a Rill,
11b Evidence, 11c Streamlit. Ossie stays the one source in every path.

## The concept

### The problem

Rill (11a) is a server that keeps the database open and answers each
click live. Evidence works the other way round: Markdown pages with SQL
in them, built into a static website. Three symptoms make it its own
lesson:

1. **Evidence has no metric language at all.** The legacy framework
   (the one this path uses) runs plain SQL that you write in
   `sources/` and in pages. Written by hand, every `SUM(...)` there is
   a second copy of a formula that lives in the Ossie document.
2. **The page is a snapshot.** Evidence runs your source SQL once, at
   `npm run sources`, and ships the answers as Parquet files inside the
   site. The reader's browser queries those files with DuckDB-WASM. A
   new matchday is invisible until someone runs the sources and the
   build again.
3. **The browser can still aggregate.** Because the reader's browser
   has a SQL engine, a page can `SUM` or `AVG` the shipped rows again.
   That is how a ratio goes wrong without anyone writing a wrong
   formula: Al Hilal's points per match across both seasons is
   102 / 41 = 2.49, but the average of the two season ratios
   (2.47 and 2.57) is 2.52.

Which Evidence: Evidence moved to "Evidence Core" in August 2026, a
binary tied to Evidence Studio, with its own `metrics/*.yaml` and no
local DuckDB file source (docs checked 2026-10-04). The open-source
framework before it, `@evidence-dev/evidence` 40.1.8, MIT, has been
frozen since 2026-02-06. It runs locally, reads `data/dawri.duckdb`,
and needs no account. This path uses the frozen one, on purpose.

### What we want

`npm run sources && npm run build` in `evidence/` produces a static
Dawri report. Its source SQL is generated from the Ossie document,
never written by hand. Every page selects and orders those rows and
never aggregates them again. One templated page per team. A parity
check proves the shipped numbers equal `dawri metrics`, and CI fails
when the generated SQL goes stale.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Static data app | SQL runs at build time; the site ships the answers as files, and the browser queries them. |
| Generated definition | A tool with no metric layer still gets one source: a generator writes its SQL from Ossie. |
| Snapshot freshness | A built site is as fresh as its last `sources` run. Freshness is a build step, not a click. |
| Pages never aggregate | Pre-computed answers can be filtered and sorted, not summed again. Re-aggregating a ratio changes its meaning. |
| Templated pages | One page file, one URL per team, prerendered from the data. |
| A frozen dependency | A package that stopped moving still installs only from its own lockfile. Pin it, or it breaks under you. |

### Before and after

```
BEFORE                                  AFTER
answers = typed commands                a static report in evidence/build
SQL written by hand in a BI tool        source SQL generated from Ossie (easy)
one table                               a season picker, one page per team (mid)
nobody compares                         evidence parity: 36 rows, 0 differences (mid)
a hand edit would drift silently        CI fails on stale SQL (hard)
```

Guardrails for every tier:

- Lesson 10's 2026/2027 freeze holds: no 2026/2027 ingest.
- The numbers do not move. Lesson 10's gates still pass unchanged.
- No metric formula is written by hand anywhere in `evidence/`. Source
  SQL is generated; page SQL selects, filters and orders, and holds no
  aggregate function.
- Deterministic only: sums and ratios of what happened.
- The Evidence project lives in `evidence/`, from the legacy template
  at commit `4b13d42` (2026-02-06), installed with `npm ci` from that
  template's `package-lock.json`. `node_modules`, `.evidence/template`
  and `build` stay out of git (the template's `.gitignore` does it).
- Telemetry is on by default: set `SEND_ANONYMOUS_USAGE_STATS=no`.
- No absolute path to your home folder in any committed file.
- `uv run pytest` still passes, `ruff` and `ty` clean.
- Gates: the target output of each tier.

---

## Easy: a report whose SQL comes from Ossie

**Target output**

```
$ mise run evidence-sync
wrote evidence/sources/dawri/team_metrics.sql: 11 metrics, by season_id and team_name

$ cd evidence && npm run sources
...
  team_metrics ✔ Finished, wrote 36 rows.
...
[INFO]:    ✅ Done!

$ npm run build
...
Build complete --> ./build

$ duckdb -csv -c "SELECT team_name, points::int AS points,
    round(points_per_match, 2) AS points_per_match
  FROM 'build/data/dawri/team_metrics/*/team_metrics.parquet'
  WHERE season_id = '0de9cda0d297418699a8357a8825d46c'
  ORDER BY points DESC LIMIT 3"
team_name,points,points_per_match
Al Nassr,86,2.53
Al Hilal,84,2.47
Al Ahli,81,2.38
```

`npm run preview` serves the built site. On its home page, 2025/2026:

```
Dawri

team_name     points  goal_difference  xg_for  xg_against
Al Nassr          86               63   64.38       21.95
Al Hilal          84               58   68.05       19.76
Al Ahli           81               46   54.19       23.04
... 18 rows, the same rows and order as uv run dawri metrics 2025/2026
```

**Spec**

1. `evidence/`: the legacy template at commit `4b13d42`, installed with
   `npm ci`. Its demo source (`needful_things`) and demo page removed.
2. A DuckDB source `evidence/sources/dawri/` on `data/dawri.duckdb`.
   The path in `connection.yaml` is relative (Reference).
3. `mise run evidence-sync` writes
   `evidence/sources/dawri/team_metrics.sql` from
   `semantic/dawri.ossie.yaml`:
   - one column per Ossie metric, same name, expression from the
     document's ANSI_SQL dialect: 11 metrics;
   - grouped by `season_id` and `team_name`, with `team_name` reached
     through the document's relationship to `dim_teams`: 36 rows;
   - a first-line comment saying the file is generated, and from what.
4. `evidence/pages/index.md`: title `Dawri`, the 2025/2026 table with
   `team_name, points, goal_difference, xg_for, xg_against`, rows and
   order as `dawri metrics`, floats at two decimals. Its SQL selects
   and orders; it does not aggregate.
5. In chat: Evidence ran your SQL once, at `npm run sources`. Tomorrow
   a new matchday lands and `dawri build` runs. What does a reader of
   the built site see, and what has to run before they see the new
   matchday? Compare with what 11a's Rill dashboard would show.

**Withheld:** how the generated SQL lets the document's qualified
expressions (`SUM(fct_team_matches.points)`) work against
`marts.fct_team_matches`. How two decimals reach the page.

---

## Mid: a season picker, a page per team, and proof

**Target output**

```
$ npm run build
...
Build complete --> ./build
$ find build/teams -name index.html | wc -l
22                                      <- 21 team pages + the list

$ mise run evidence-parity
evidence parity 2025/2026: 18 teams, 0 differences
evidence parity 2026/2027: 18 teams, 0 differences
```

The home page now has a season picker (2026/2027 first, the live
season). Switching it re-queries in the browser, with no rebuild:

```
Season  [2026/2027 v]
team_name     points  goal_difference  xg_for  xg_against
Al Hilal          18               18   25.08        8.27
Al Ittihad        17                6   14.12        9.96
Al Nassr          16                9   11.96        5.70
```

`/teams/Al Hilal`:

```
Al Hilal

season_id   matches_played  points  points_per_match  goal_difference  xg_for  xg_against
2025/2026               34      84              2.47               58   68.05       19.76
2026/2027                7      18              2.57               18   25.08        8.27
```

**Spec**

6. A season picker on the home page, defaulting to 2026/2027. The
   table follows it. Seasons show as `2025/2026`, not as ids.
7. `/teams`: every team that appears in the data, by name, each
   linking to its page. `/teams/[team]`: one templated page per team,
   one row per season the team played, the columns of the target
   output. Teams with one season have one row. 21 pages.
8. No page aggregates. A "both seasons" total is out of scope for this
   path: Ossie has no answer for it in the shipped rows, so the page
   does not invent one.
9. `mise run evidence-parity`: read the Parquet the build ships, and
   compare every team's eleven metrics with `dawri metrics --metric`
   for all eleven, both seasons, floats at two decimals. Print the two
   lines in the target output. Exit 1 on any difference, on a team
   present on one side only, or when there is no build.
10. If you built 11a mid, the source reads 11a's serving copy instead
    of `data/dawri.duckdb`, so `npm run sources` never meets a running
    build on the lock.

**Withheld:** how a season id becomes `2025/2026` on the page without
writing a formula. How a templated page knows which team it is. Where
the parity check finds the Parquet (its folder name is a hash).

---

## Hard (optional): the generated SQL cannot drift

**Target output**

```
$ mise run evidence-sync -- --check; echo $?
0

$ (branch: a SUM edited by hand in team_metrics.sql, pushed)
$ gh run list --limit 1
completed  failure  ...    <- evidence-sync: evidence/sources/dawri/team_metrics.sql is stale
(branch deleted after)
```

**Spec**

11. A check mode, `mise run evidence-sync -- --check`, regenerates in
    memory and exits 1 with
    `evidence/sources/dawri/team_metrics.sql is stale` when the
    committed file differs. It never writes the file. CI runs it on
    every push. CI does not install Evidence (858 MB). Prove it red
    with the branch, then delete the branch.
12. A second check, in the same task or its own: no file in
    `evidence/pages/` contains an aggregate function (`SUM(`, `AVG(`,
    `COUNT(`, `MIN(`, `MAX(`). Exit 1 naming the file.
13. In chat: write the page query that turns Al Hilal's
    points_per_match into 2.52 for "both seasons". Then say why 2.49 is
    the only answer Ossie's definition allows, and what the page would
    need from the source to show it.

**Withheld:** whether the check and the generator share one function.

---

## Reference

### The legacy framework (checked 2026-10-05)

```
@evidence-dev/evidence         40.1.8   2026-02-06  MIT  (last release)
@evidence-dev/core-components  5.4.2    2026-02-06
@evidence-dev/duckdb           2.0.1    2026-02-06  bundles @duckdb/node-api 1.4.2-r.1
template                       github.com/evidence-dev/template, commit
                               4b13d42 (2026-02-06); the repo's main
                               branch moved to Evidence Core on 2026-08-20
node                           26.7.0 on this machine; engines ">=18"
```

Getting the template at that commit:

```
gh api repos/evidence-dev/template/tarball/4b13d42 > template.tgz
mkdir evidence && tar xzf template.tgz -C evidence --strip-components=1
cd evidence && npm ci
```

`npm ci`: 1,311 packages, `node_modules` 858 MB, 28 s. `npm install`
without the lockfile fails: `ERESOLVE ... Found: typescript@7.0.2 ...
peer typescript@"^4.9.4 || ^5.0.0" from svelte2tsx@0.7.4`. The frozen
package no longer resolves against today's npm. The lockfile is the
only working install.

```
npm run sources     runs every sources/<name>/*.sql, writes Parquet
npm run build       static site in build/ (24.8 s, 87 MB, almost all JS)
npm run dev         dev server with reload
npm run preview     serves build/
```

### DuckDB source

```yaml
# sources/<name>/connection.yaml
name: <name>
type: duckdb
options:
  filename: <path>      # relative to this source folder
```

`../../../data/dawri.duckdb` from `evidence/sources/dawri/` reaches the
repo's `data/` (checked). The driver opens the file `READ_ONLY`, for the
seconds `npm run sources` takes. DuckDB 1.4.2 inside the driver read
the 1.5.5 file without complaint (checked). In page SQL a source table
is `<source>.<query file name>`, here `dawri.team_metrics`.

### What the build ships

```
.evidence/template/static/data/dawri/team_metrics/team_metrics.parquet
                                       after npm run sources
build/data/dawri/team_metrics/<hash>/team_metrics.parquet
                                       after npm run build
```

Integer sums arrive as DOUBLE in the Parquet (`86.0`): DuckDB's `SUM`
over integers is HUGEINT, and the driver writes it as a double. Cast or
format on the way out. Floats are unrounded (`64.3775`).

### Pages (legacy syntax)

````markdown
```sql name
select ... from dawri.team_metrics where ...
```

<DataTable data={name}>
  <Column id=xg_for fmt=num2/>
</DataTable>

<Dropdown name=season data={seasons} value=season_id label=season/>
... where season_id = '${inputs.season.value}'

pages/teams/[team].md        one page per value; {params.team} inside
````

A templated page is prerendered for every link the build finds to it,
so a list page that links each team is what makes the build write 21
pages (checked: 22 `index.html` files under `build/teams`).

Telemetry: `@evidence-dev/telemetry` sends anonymous usage unless
`SEND_ANONYMOUS_USAGE_STATS` is `no` (default `yes`, read in
`telemetry/index.cjs`).

### Numbers on the real data (landed 2026-09-25)

```
team_metrics              36 rows (18 teams x 2 seasons, 21 teams)
2025/26 top 3             Al Nassr 86 (2.53), Al Hilal 84 (2.47),
                          Al Ahli 81 (2.38)
Al Hilal 2026/27          7 played, 18 pts, 2.57 per match, +18,
                          xG 25.08 - 8.27
Al Hilal both seasons     102 pts / 41 played = 2.49 (Ossie's ratio)
                          average of 2.47 and 2.57 = 2.52 (wrong)
```
