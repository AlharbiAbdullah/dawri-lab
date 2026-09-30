# L13: from insight to action (the actuator)

## The concept

### The problem

> "Sensors without actuators are useless."
> Mike Driscoll (Rill), in the Joe Reis interview in your notes

Dawri senses (ingest), knows (marts, one metric definition), shows (a
dashboard) and answers (an API). It never does anything. Three
symptoms:

1. **Nothing happens when something happens.** On 2026-10-09 Matchday
   8 starts: nine matches, first against second on the Saturday. When
   those results land, Dawri will know them within one run, and nobody
   will hear about it until someone opens a dashboard and thinks to
   look.
2. **Every insight waits for a person to ask.** The facts a fan wants
   before a matchday (both teams' position, form, xG per match, their
   record against each other) are all in the marts. Putting them side
   by side takes four queries and a person who knows them.
3. **Acting twice is as bad as never acting.** A run happens every day
   (or twice, or retried). An actuator that announces the same result
   at every run is noise, and one that loses track after a failed send
   announces nothing. "Once per fact" needs a memory of what was done.

### What we want

Before each matchday, Dawri writes a fixture brief: facts only, one
block per match. After each run, Dawri writes a result note for every
match that finished since it last acted. Each goes out once, through
one channel, and a failed delivery is retried on the next run, never
duplicated. In the hard tier, a timer runs the whole loop daily, and an
AI may write the prose, but only numbers that are in the facts get
through.

### What you will understand at the end

| Idea | In one line |
|---|---|
| Actuator | The part of a system that changes something outside it. Here: a message someone receives. |
| Change detection | Acting on what is new since last time, not on everything that is true. |
| Idempotent action | Run it twice, act once. The ledger of what was done is part of the product. |
| At-least-once delivery | Mark done after the send succeeds, not before. A crash between the two means a resend, never a loss. |
| AI with a fact guard (hard) | The model writes words; a deterministic check owns the numbers. |

### Before and after

```
BEFORE                                  AFTER
results known, nobody told              result note per newly finished match (mid)
pre-matchday facts need four queries    dawri brief: one file per matchday (easy)
xG per match computed ad hoc            two new metrics in the one definition (easy)
no memory of what was sent              action ledger: once per fact (mid)
someone must run it                     systemd timer, daily (hard)
prose by hand or not at all             AI prose, every number checked (hard)
```

Guardrails for every tier:

- Facts only. Every number in a brief or a note is computed from landed
  data. No prediction, no odds, no "favourite", no "should win".
  Words like "form" mean the last five results, printed, nothing more.
- Numbers come from one place. A number that is a metric comes from the
  lesson 10 definitions. A number that is not (last five results,
  head-to-head list) comes from the marts. Nothing is recomputed from
  raw.
- Nothing leaves the machine unless `DAWRI_NOTIFY_URL` is set. Without
  it, every action is a file in `<DAWRI_DATA_DIR>/outbox/`, and the
  tests never set it to a real address.
- Tests never open a socket, never sleep, and never call an AI.
- `uv run pytest` passes, `ruff` and `ty` clean.
- Gates: the target output of each tier.

---

## Easy: the fixture brief

**Target output**

```
$ uv run dawri build
... Summary: 61 total | 61 success

$ mise run ossie
Written to semantic/dawri.ossie.yaml
dawri 0.2.0.dev0: 2 datasets, 1 relationships, 13 metrics

$ uv run dawri brief 2026/2027
data/outbox/brief-2026-2027-md-8.md

$ head -24 data/outbox/brief-2026-2027-md-8.md
(see Reference: "The brief on the real data", exact)

$ uv run pytest
<previous count + 2> passed
```

**Spec**

1. Two metrics added to the one definition, in `_semantic.yml`, then
   `mise run ossie`:

   | metric | type | definition | label |
   |---|---|---|---|
   | `xg_for_per_match` | ratio | `xg_for` over `matches_played` | xG for per match |
   | `xg_against_per_match` | ratio | `xg_against` over `matches_played` | xG against per match |

   Lessons 10 and 11 now count 13 metrics wherever they said 11. If
   you built lesson 11's hard tier, `mise run rill-sync` picks them up
   with no other change. That is the point of it.
2. `dawri brief SEASON` writes the brief for the season's next
   matchday: the matchday of the earliest UPCOMING match. It prints the
   path it wrote, and nothing else, on stdout. Running it twice writes
   the same bytes.
   - File: `<DAWRI_DATA_DIR>/outbox/brief-<season>-<md>.md`, season as
     `2026-2027`, md from the matchday's short name (`MD 8` -> `md-8`).
   - A season with no UPCOMING match: exit 1, `no upcoming matchday in
     <season>` on stderr, no file.
3. The brief's content, Markdown, in this order:
   - `# <matchday name>, <season>`
   - One line: `<n> matches, <first kickoff day> to <last kickoff
     day>. Facts from <n> finished matches of <season>. Times are
     Riyadh (UTC+3).` Days as `Fri 2026-10-09`.
   - One block per match in kickoff order (then home team name):

     ```
     ## <home> v <away>
     <Day date HH:MM>, <stadium>

     |  | <home> | <away> |
     |---|---|---|
     | Position | <rank> | <rank> |
     | Points | ... | ... |
     | Played | ... | ... |
     | W-D-L | 6-0-1 | ... |
     | Goals | 23-5 | ... |
     | xG for per match | 3.58 | ... |
     | xG against per match | 1.18 | ... |
     | Last 5 | W L W W W | ... |

     <head-to-head line>
     - <date> <home> <score> <away>          one line per meeting, oldest first
     ```

   - Position is `mart_standings` rank (type `table`). Teams level on
     every criterion `mart_standings` ranks by share the better
     position, written `=2`. A team with no finished match has `-` in
     every row.
   - Last 5: that team's results, most recent first, space separated,
     fewer when fewer were played.
   - Head-to-head line: `Head to head in the data: <n> matches. <home>
     <w> wins, <d> draws, <away> <w> wins.` or `Head to head in the
     data: none.` It covers every season in the data.
   - xG with two decimals. No other rounding anywhere.
4. Two tests on the recorded data:

   ```
   test_brief_recorded       brief 2026/2027 on the recorded data equals
                             the recorded brief in Reference, byte for byte
   test_brief_no_upcoming    brief 2025/2026 on the recorded data: exit 1,
                             no file
   ```

5. In chat: read your real Matchday 8 brief as a fan would. Which one
   line carries the most information about the Al Hilal v Al Ittihad
   match, and which number in the whole brief is most likely to
   mislead, and why? Facts from the brief only.

**Withheld:** how the brief gets its metric numbers through the lesson
10 code instead of new SQL. How "level on every criterion" is found
without copying `mart_standings`' `order by`. How the Markdown is built
so that the same data always gives the same bytes.

---

## Mid: act on what changed, once

**Target output**

```
$ uv run dawri act --init
ledger: 63 results marked done, 0 sent

$ uv run dawri act
sent: brief-2026-2027-md-8
ledger: 1 sent, 0 failed

$ uv run dawri act
ledger: 0 sent, 0 failed

(after Matchday 8 is played and dawri run has landed it)
$ uv run dawri act
sent: result-a10a6c353d734675b6e000b253df6335
... (one line per newly finished match)
sent: brief-2026-2027-md-9
ledger: 10 sent, 0 failed

$ uv run pytest
<easy count + 5> passed
```

**Spec**

6. `dawri act` looks at the database and the action ledger, and for
   each action not yet done, in this order:
   - a **result note** for every FINISHED match of the live season
     that the ledger has not marked done, in kickoff order;
   - the **brief** for the live season's next matchday, if the ledger
     has not marked that brief done.

   It prints one `sent: <action id>` line per action delivered, then
   `ledger: <n> sent, <n> failed`. Action ids: `result-<match id>`,
   `brief-<season>-<md>`.
7. `dawri act --init` marks every FINISHED match of the live season
   done without sending anything, and prints `ledger: <n> results
   marked done, 0 sent`. It is how the actuator starts from today
   instead of announcing the whole season. `dawri act` on a ledger
   that was never initialised exits 1 and says to run `--init` first.
8. The result note, Markdown:

   ```
   # <home> <h>-<a> <away>
   <season>, <matchday name>, <Day date HH:MM> Riyadh, <stadium>

   Goals: <minute>' <player> (<team>), ... .      or  Goals: none.
   <home> now <points> pts from <played> matches. <away> now <points> pts from <played> matches.
   ```

   The goals line ends with a full stop, as in the recorded note in
   Reference. Minutes in added time as `90+3'`. An own goal names the scorer and
   the team the goal counted for, followed by ` (og)`. Singular `pt`
   and `match` when the number is 1.
9. Delivery: every action is written to `<DAWRI_DATA_DIR>/outbox/<action
   id>.md`. When `DAWRI_NOTIFY_URL` is set, it is also POSTed there:
   the Markdown as the body, the note's first line (without `# `) as a
   `Title` header. That is the ntfy.sh message format, and any webhook
   that reads a body works. An action is marked done only after its
   delivery succeeded. A failed POST (non-2xx or no connection) is
   counted in `failed`, left not done, and tried again on the next
   run. `dawri act` exits 1 when anything failed.
10. The ledger survives `dawri load`, `dawri build` and a deleted
    `outbox/`. Deleting the outbox never causes a resend.
11. Five tests on the recorded data, sockets blocked, the notify URL
    answered by a fake (lesson 9's tools):

    ```
    test_act_needs_init          act before --init: exit 1, nothing sent
    test_act_init_sends_nothing  --init: "2 results marked done, 0 sent"
    test_act_brief_once          after --init: act sends brief-2026-2027-md-8;
                                 act again sends nothing
    test_act_result_note         after --init, fed56 unmarked in the ledger:
                                 act sends result-fed56... equal to the
                                 recorded note in Reference, byte for byte
    test_act_retries_failed      notify URL answers 500: failed 1, not done;
                                 next act with 200: sent 1; third act: 0
    ```

**Withheld:** where the ledger lives, given that `data/dawri.duckdb`
is rebuilt and locked by other readers. How "mark done after the send"
survives a crash between the two. How a test "unmarks" one action
without reaching into your ledger's internals, or whether it should.

---

## Hard (optional): it runs itself, and an AI may write the words

**Target output**

```
$ systemctl --user list-timers dawri.timer
NEXT                         LEFT      LAST  PASSED  UNIT         ACTIVATES
Thu 2026-10-01 06:00:00 +03  ...       -     -       dawri.timer  dawri.service

$ systemctl --user start dawri.service; journalctl --user -u dawri.service -n 3 -o cat
... ingest end ...
... act end ...
ledger: 0 sent, 0 failed

$ uv run dawri brief 2026/2027 --prose
data/outbox/brief-2026-2027-md-8.md
prose: 9 fixtures, 9 kept, 0 rejected

$ (a planted draft: "Al Hilal have 19 points" for the Al Hilal v Al Ittihad block)
prose: 9 fixtures, 8 kept, 1 rejected
rejected Al Hilal v Al Ittihad: 19 not in facts
```

**Spec**

12. `deploy/systemd/dawri.service` and `deploy/systemd/dawri.timer`,
    committed, installed as user units. The service runs
    `dawri run 2026/2027` then `dawri act`, the second only if the
    first succeeded, from the repo root with the repo's environment.
    The timer fires daily at 06:00 Riyadh time and catches up a run
    missed while the machine was off. How to install them goes in the
    README, three commands at most.
13. `dawri brief SEASON --prose` adds, under each match block's
    heading, a paragraph of at most three sentences written by an AI
    from that match's facts only. The facts go to the model as JSON:
    every number in the block, nothing else.
14. The fact guard: every number in a paragraph (integers, decimals,
    scores like `2-0`, positions like `=2`) must appear in that
    match's facts JSON. A paragraph with any other number is dropped,
    that block is written without prose, and stderr names the match and
    the first offending number. The last line on stderr is `prose: <n>
    fixtures, <n> kept, <n> rejected`.
15. Tests for the guard only, with hand-written paragraphs, no model
    call:

    ```
    test_guard_keeps_true_numbers    "Al Hilal sit 1st on 18 points"      kept
    test_guard_rejects_new_number    "Al Hilal have 19 points"            rejected, 19
    test_guard_rejects_derived       "a one-point gap"                    rejected, 1?
    test_guard_score_and_decimal     "won 2-0 ... 3.58 xG per match"      kept
    ```

    `test_guard_rejects_derived` has a question in it: "one" is a word,
    and 18 - 17 = 1 is true but not in the facts. Decide what the guard
    does with number words and with true arithmetic, write it in the
    test's docstring, and defend it in chat.
16. In chat: the guard checks that numbers are in the facts, not that
    the sentence around them is true. Write one paragraph that passes
    your guard and is false, and say what a second check would need to
    catch it.

**Withheld:** which model and how it is called (the API with a key,
or `claude -p` headless on this machine). How numbers are found in
text. How a unit file gets the repo's environment.

---

## Reference

### The brief on the real data (landed 2026-09-25), first 24 lines

```
# Matchday 8, 2026/2027

9 matches, Fri 2026-10-09 to Sun 2026-10-11. Facts from 63 finished matches of 2026/2027. Times are Riyadh (UTC+3).

## Al Kholood v Al Qadsiah
Fri 2026-10-09 16:50, Al Hazem Club Stadium

|  | Al Kholood | Al Qadsiah |
|---|---|---|
| Position | 6 | 4 |
| Points | 12 | 16 |
| Played | 7 | 7 |
| W-D-L | 3-3-1 | 5-1-1 |
| Goals | 12-10 | 16-8 |
| xG for per match | 1.58 | 2.35 |
| xG against per match | 1.17 | 0.96 |
| Last 5 | L W D W D | D W W W W |

Head to head in the data: 2 matches. Al Kholood 0 wins, 0 draws, Al Qadsiah 2 wins.
- 2025-11-06 Al Qadsiah 4-0 Al Kholood
- 2026-03-07 Al Kholood 1-4 Al Qadsiah

## Al Fateh v Al Ahli
```

The Saturday headline block, for step 5:

```
## Al Hilal v Al Ittihad
Sat 2026-10-10 21:00, Kingdom Arena

|  | Al Hilal | Al Ittihad |
|---|---|---|
| Position | 1 | 2 |
| Points | 18 | 17 |
| Played | 7 | 7 |
| W-D-L | 6-0-1 | 5-2-0 |
| Goals | 23-5 | 12-6 |
| xG for per match | 3.58 | 2.02 |
| xG against per match | 1.18 | 1.42 |
| Last 5 | W L W W W | W W W D W |

Head to head in the data: 2 matches. Al Hilal 1 wins, 1 draws, Al Ittihad 0 wins.
- 2025-10-24 Al Ittihad 0-2 Al Hilal
- 2026-02-21 Al Hilal 1-1 Al Ittihad
```

(`1 wins, 1 draws` is the spec as written: plural always, in the
head-to-head line only. Keep it or change the spec and the tests
together, and say which in chat.)

Matchday 8, all nine, kickoff UTC (Riyadh is +3):

```
Fri 13:50  Al Kholood v Al Qadsiah      Al Hazem Club Stadium
Fri 14:55  Al Fateh v Al Ahli           MaydanTamweel Aloula
Fri 18:00  Al Nassr v Diriyah           Al-Awwal Park
Sat 13:50  Al Hazem v NEOM SC           Al Hazem Club Stadium
Sat 14:55  Al Ettifaq v Al Khaleej      Al Ettifaq Club Stadium
Sat 18:00  Al Hilal v Al Ittihad        Kingdom Arena
Sun 13:40  Al Fayha v Al Riyadh         Al Majma'a Sport City Stadium
Sun 15:25  Abha v Al Faisaly            Dhamak Club Stadium
Sun 18:00  Al Shabab v Al Taawoun       SHG Arena
```

For UPCOMING matches the API gives `utc_offset` `+00:00` and a local
time equal to UTC, so the Riyadh time is computed, not read. Kickoff
times of unplayed matches can still move; the brief shows what the
data says on the day it is written.

The live table on the real data has no two teams level on every
criterion. `=` never appears in the real brief.

### The brief on the recorded data (test_brief_recorded)

```
# Matchday 8, 2026/2027

1 matches, Fri 2026-10-09 to Fri 2026-10-09. Facts from 2 finished matches of 2026/2027. Times are Riyadh (UTC+3).

## Al Kholood v Al Qadsiah
Fri 2026-10-09 16:50, Al Hazem Club Stadium

|  | Al Kholood | Al Qadsiah |
|---|---|---|
| Position | =2 | - |
| Points | 1 | - |
| Played | 1 | - |
| W-D-L | 0-1-0 | - |
| Goals | 1-1 | - |
| xG for per match | 1.41 | - |
| xG against per match | 0.56 | - |
| Last 5 | D | - |

Head to head in the data: none.
```

Diriyah and Al Kholood drew 1-1 and are level on points, head-to-head,
goal difference and goals for, so both are `=2`. `mart_standings`
gives them ranks 2 and 3 in an order its `order by` does not decide
(lesson 12, step 10). The header's `1 matches` follows the spec as
written; if you make it singular, change the spec line here too.

### The result note on the recorded data (test_act_result_note)

```
# Diriyah 1-1 Al Kholood
2026/2027, Matchday 3, Wed 2026-08-26 21:00 Riyadh, Al-Awwal Park

Goals: 71' Al Elewa (Al Kholood), 83' Al Nemr (Diriyah).
Diriyah now 1 pt from 1 match. Al Kholood now 1 pt from 1 match.
```

### ntfy

`POST https://ntfy.sh/<topic>` with the message as the body and a
`Title:` header publishes to everyone subscribed to that topic. Topics
are public by name: pick one nobody would guess, or self-host. The spec
only needs "a URL that accepts a POST"; ntfy is the one to try it with.

### systemd user units

`systemctl --user daemon-reload`, `systemctl --user enable --now
dawri.timer`, `systemctl --user list-timers`. `OnCalendar=` with a
time zone (`*-*-* 06:00:00 Asia/Riyadh`), `Persistent=true` for missed
runs. `journalctl --user -u dawri.service` for the log.
