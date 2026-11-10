# KaiaRX

Kaia's radio, without the Discord bot. Two receivers in one:

- **A local scanner** on an RTL-SDR USB dongle. It sweeps the voice bands (2 m and 70 cm
  ham, VHF/UHF business, FRS/GMRS, MURS, marine, NOAA, railroad), holds on anything that
  keys up, follows a conversation into one recording, tells voice from data, packet,
  bare carriers and static, transcribes speech locally (faster-whisper, CPU), and keeps
  a ledger and a band notebook of what lives where. Watch it in **KAIA//RX**, the
  browser dashboard: band waterfalls, click to tune, listen live, ▶ SCAN.
- **Shortwave through public KiwiSDRs**: scheduled listening for the USAF HFGCS (8992
  kHz, with phonetic parsing of Emergency Action Messages and a cross-check against
  eam.watch), number stations on Priyom's schedule, and UVB-76 "The Buzzer" samples.
  Receivers that refuse, or send silence on a frequency, are remembered and skipped.

It is the radio subsystem of [Kaiacord](../Kaiacord) (Kaia, a self-hosted Discord bot),
running the very same code; this repo adds a command-line entry point and a few small
stand-ins for what the bot provided.

## Install

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python tools/maintenance/fetch_radio_assets.py   # kiwiclient (KiwiSDR recorder) + the speech model
```

The local scanner needs `librtlsdr` (Arch: `rtl-sdr`, Debian: `librtlsdr0`) and an
RTL2832U dongle; the shortwave side needs only the internet. `ffmpeg` is used for clips.

## Use

```bash
venv/bin/python kaiarx.py run --window   # dashboard + nightly scanner + scheduled KiwiSDR listens
venv/bin/python kaiarx.py dash           # just the dashboard; ▶ SCAN sweeps while the page is open
venv/bin/python kaiarx.py record 8992 usb 120 --region na   # one KiwiSDR recording
venv/bin/python kaiarx.py uvb76          # one UVB-76 sample
venv/bin/python kaiarx.py notebook       # rewrite docs/reports/reference/local_band_notebook.md
venv/bin/python kaiarx.py status
```

Maintenance tools (shared with Kaiacord):

```bash
venv/bin/python tools/maintenance/fetch_street_names.py "Your County" --write  # street list for dispatch transcripts
venv/bin/python tools/maintenance/ledger_repair.py --clips --streets           # bring the ledger up to today's judging; --apply writes
venv/bin/python tools/maintenance/band_notebook.py --write                     # same as `kaiarx.py notebook`
```

`fetch_street_names.py` queries OpenStreetMap once and writes the git-ignored
`memory/radio/streets.json`; the scanner corrects misheard street names in dispatch transcripts
against it. Without it, transcripts are left as heard.

Settings: copy what you want to change from `config/default_config.yaml` into
`config/local.yaml` — scan hours, gain, dongle ppm, your local repeaters and nets,
which number stations to follow, the dashboard port (47442).

## Working on it (and getting the work back into Kaiacord)

Most of the code is **shared with Kaiacord byte-for-byte** (listed in `sync.json`).
Improve it here, test it here, then:

```bash
python3 sync.py status   # what changed, on which side
python3 sync.py push     # copy your changes into ../Kaiacord (then test and commit there)
python3 sync.py pull     # take Kaiacord's changes
```

Rules for AI agents and people alike are in [CLAUDE.md](CLAUDE.md).

## Licence

The code is Kaiacord's (MIT, see Kaiacord). kiwiclient (GPL) is fetched at install time
and never committed; the speech model is downloaded by faster-whisper.
