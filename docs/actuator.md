# Fixture briefs and result delivery

```sh
uv run dawri brief 2026/2027
uv run dawri act --init
uv run dawri act
```

`brief` finds the earliest upcoming match and writes its whole matchday to
`data/outbox/brief-2026-2027-md-N.md`. Repeating it against the same published
generation writes identical bytes. Times are computed from UTC in Asia/Riyadh.
Shared positions come from dbt's sporting rank. The two xG ratios come through
Ossie; the brief does not define a second metric expression.

Initialize once before the first normal actuator run. `--init` marks the live
season's existing results done without writing or sending notes. Repeating it
also suppresses any results that have arrived since the previous initialization.

`act` queues unseen finished matches, then the next brief. Every action writes
Markdown to the outbox. By default that local file is the delivery. Setting
`DAWRI_NOTIFY_URL` additionally sends an HTTP POST with the Markdown body,
`Title` and `Idempotency-Key` headers. Configure a real destination only when
ready to publish to its subscribers. Tests use fake URLs with sockets blocked.

`data/actions.sqlite3` holds pending payloads and successful action identifiers.
It survives warehouse rebuilds and outbox deletion. Each successful delivery
commits its mark immediately. Failures remain pending, including an older brief
whose matchday is no longer next. A file lock serializes overlapping actuator
runs. A crash after POST and before its mark can resend that action; a receiver
must honor the idempotency key to suppress that duplicate.

## Optional prose

```sh
uv run dawri brief 2026/2027 --prose
```

The local Ollama daemon calls an existing cloud model,
`deepseek-v4.1-flash:cloud`. `DAWRI_PROSE_MODEL` overrides its name. This requires
a signed-in Ollama installation. No model or key is downloaded by Dawri.
Each call receives only one fixture block's facts as JSON. Provider failures,
more than three sentences, multiple paragraphs, or unknown numbers drop that
paragraph. The factual block still prints. Rejections and totals go to stderr.

The guard accepts numeric tokens already present in that fixture's facts,
including score components, decimals and ordinal digits. It rejects number words
such as “one”, even when the arithmetic would be true: deriving a gap is outside
this guard's contract. It checks membership, not the relationship between team,
measure and number. With Al Hilal on 18 and Al Ittihad on 17, “Al Ittihad have
18 points” passes and is false. Catching that requires checking the claim's team,
metric and value together. Keep the tables as the authoritative facts.

## Daily run

The user service runs the live pipeline, then acts only when the pipeline
succeeds. The committed timer runs at 06:00 Asia/Riyadh with missed-run catch-up.
Install from the checkout with the three README commands. It assumes the checkout
is at `$HOME/projects/dawri-lab`, with uv in the mise shims and dbt available
through the project environment. It writes local files unless a notification
URL is deliberately added to the service environment. It does not request prose.

```sh
systemctl --user list-timers dawri.timer
systemctl --user start dawri.service
journalctl --user -u dawri.service -n 10 -o cat
systemctl --user disable --now dawri.timer  # stop scheduled refreshes
```
