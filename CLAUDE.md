# CLAUDE.md — KaiaRX

KaiaRX is Kaia's radio from the Kaiacord Discord bot, runnable on its own: an RTL-SDR
waterfall scanner that holds, records, classifies and transcribes what it hears (with
the KAIA//RX browser dashboard), and scheduled listening through public KiwiSDR
receivers (HFGCS, number stations, UVB-76). **Kaiacord is the mother project.** This
repo exists so the radio can be worked on, tested and used without the bot, and every
improvement goes back to Kaiacord.

## The one rule: shared files stay byte-identical with Kaiacord

`sync.json` lists the **shared files** (most of `utils/`, `assets/rx/`, some tools and
tests). They are copies of Kaiacord's files at the same relative path, and the same file
runs in both places. Everything else is **standalone-only** and says so in its header.

| Shared (edit carefully, it runs in Kaiacord too) | Standalone-only (this repo's own) |
|:--|:--|
| `utils/radio/*`, `utils/infrastructure/logging/*`, `utils/core/atomic_write.py`, … (see `sync.json`) | `kaiarx.py` (entry point), `standalone/` (bootstrap, discord stand-in), `utils/infrastructure/system/yaml_config.py`, `config/`, `conftest.py`, `sync.py`, docs |

So, for a shared file:

- **Don't add standalone hacks to it.** If the standalone needs different behaviour, put it
  in a standalone-only file (the entry point, `standalone/`, the config loader) — or make
  the shared code configurable through `config.get(...)` with Kaiacord's default unchanged.
- **Don't rename or move it** without doing the same in Kaiacord (and `sync.json`).
- **It must still work inside Kaiacord**, where `discord` is the real library and the bot,
  Ollama and the voice thread are running. Kaiacord's rules for this code apply here
  unchanged: read `docs/kaiacord/CLAUDE.md` (a read-only copy, refreshed by `sync.py pull`):
  §7 "The local scanner" and the radio/KiwiSDR paragraphs, §9 (logging, telemetry that
  lies, check the payload), §11 (working practice).
- New shared files: add them in Kaiacord first (or here, then list them in `sync.json`
  and push), so both sides have them.

## Workflow

```bash
python3 sync.py pull                 # before starting: take Kaiacord's latest
# … work, then test here:
venv/bin/python -m pytest -q
python3 sync.py status               # what you changed (local), what Kaiacord changed (upstream)
python3 sync.py push                 # send your shared-file changes to ../Kaiacord
# then in Kaiacord: run its suite and commit there (its CLAUDE.md §2, §13)
```

`sync.lock.json` records each shared file's hash at the last sync (commit it; never edit
it by hand). A file changed on both sides is a **conflict**: merge by hand, then
`sync.py pull --force PATH` or `push --force PATH`. A push never deletes a file in
Kaiacord unless named with `--force`.

## Tests

`venv/bin/python -m pytest -q` runs Kaiacord's radio tests unchanged (`tools/tests/`,
shared) plus this repo's own (`tests/`). A shared test that needs a Kaiacord-only module
(the Discord panel, the morning post) is reported as *skipped: Kaiacord-only*, by
`conftest.py`; any other failure is real. Add tests for shared code to the shared test
files (or a new shared test file) so Kaiacord runs them too.

## Running

`python3 kaiarx.py --help`. Settings in `config/local.yaml` override
`config/default_config.yaml` (same keys as Kaiacord's `radio:` section). Data goes to
`memory/radio/` and logs to `logs/kaiarx.log`, both git-ignored. Don't run KaiaRX's
scanner and Kaiacord's at the same time on one dongle: each holds the RTL-SDR while
it scans.

## Verify behaviour, not just syntax

As in Kaiacord: a change is done when you have watched it work — a real sweep on the
dongle (`kaiarx.py dash`, ▶ SCAN), a real KiwiSDR recording (`kaiarx.py record`), the
clip listened to or measured, the ledger row read — not when the tests pass.
