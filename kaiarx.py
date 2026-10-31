#!/usr/bin/env python3
"""KaiaRX — Kaia's radio, without the Discord bot.

STANDALONE-ONLY FILE: the entry point. Everything it drives is Kaiacord's own code
(utils/radio/, shared byte-for-byte; see sync.py).

    python3 kaiarx.py run            receiver dashboard + nightly RTL-SDR watch + scheduled KiwiSDR listens
    python3 kaiarx.py run --window   … and open the dashboard as an app window
    python3 kaiarx.py dash           the dashboard alone (tune, ▶ SCAN, listen in the browser)
    python3 kaiarx.py record 4625 usb 60 [--region eu]   one KiwiSDR recording into recordings/
    python3 kaiarx.py uvb76          one UVB-76 sample (S-meter + clip) into memory/radio/uvb76/
    python3 kaiarx.py notebook       rewrite the band notebook from the ledger
    python3 kaiarx.py status         what the ledger and the receiver health hold

`run` is what Kaiacord's radio task does every minute (feeds, cross-check, scheduled
listens, the nightly watch), minus posting to Discord: catches are printed here and
kept in memory/radio/ as they are there. Settings: config/default_config.yaml,
overridden by config/local.yaml.
"""
from __future__ import annotations

import standalone.bootstrap  # noqa: F401  (working directory, log file, discord stand-in)

import argparse
import asyncio
import signal
import sys
from pathlib import Path


def _say(text: str) -> None:
    print(text, flush=True)


async def _post(entry: dict) -> bool:
    """Kaiacord posts a catch to a channel; here it is printed."""
    what = entry.get("transcript") or "(no words)"
    _say(f"[{entry.get('started', '')[:16]}] {entry.get('station')} {entry.get('khz'):g} kHz via "
         f"{entry.get('receiver_location') or entry.get('receiver')}: {what[:200]}  clip: memory/radio/clips/{entry.get('clip')}")
    return True


async def _radio_minute(local: bool, web: bool) -> None:
    from utils.infrastructure.logging.kaia_logger import log_error, log_info, log_warning
    from utils.infrastructure.system.yaml_config import config
    from utils.radio import eam_watch, priyom, scanner, transcribe, watch
    from utils.radio.fetch import FeedError
    if web and config.get("radio.enabled", True):
        poll = float(config.get("radio.poll_hours", 6)) * 3600
        for name, refresh in (("eam.watch", eam_watch.refresh), ("priyom", priyom.refresh)):
            try:
                cache = await refresh(poll)
                if name == "eam.watch" and (n := watch.cross_check(eam_watch.messages(cache))):
                    log_info(f"[radio] cross-checked {n} transcription(s) against eam.watch")
            except FeedError as e:
                log_warning(f"[radio] {name} refresh failed: {e}")
            except Exception as e:
                log_error(f"[radio] {name} refresh error: {e}")
        try:
            await watch.tick(poster=_post)
        except Exception as e:
            log_error(f"[radio] scheduled listen failed to start: {e}")
        transcribe.release_if_idle()
    if local:
        try:
            if scanner.tick():
                _say("[scanner] the watch started (nightly hours, a net, or a scan asked for)")
        except Exception as e:
            log_error(f"[scanner] tick failed: {e}")


async def _serve_dashboard(window: bool) -> str:
    from utils.radio import rx_dashboard
    url = rx_dashboard.serve()
    if url and window:
        await asyncio.to_thread(rx_dashboard.open_window)
    return url


async def cmd_run(a) -> int:
    from utils.radio import scanner
    url = await _serve_dashboard(a.window) if not a.no_dashboard else ""
    if url:
        _say(f"KAIA//RX dashboard: {url}")
    from utils.infrastructure.system.yaml_config import config
    _say(f"nightly watch hours {config.get('radio.local.hours')} (config radio.local.hours); "
         f"web listens {'on' if not a.no_web else 'off'}; Ctrl+C to stop")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    while not stop.is_set():
        await _radio_minute(local=not a.no_local, web=not a.no_web)
        try:
            await asyncio.wait_for(stop.wait(), 60)
        except asyncio.TimeoutError:
            pass
    _say("stopping: releasing the dongle and any receiver slot…")
    await scanner.shutdown()
    return 0


async def cmd_dash(a) -> int:
    url = await _serve_dashboard(not a.no_window)
    _say(f"KAIA//RX dashboard: {url}  (▶ SCAN starts the watch while the page is open; Ctrl+C to stop)")
    a.no_local, a.no_web, a.no_dashboard, a.window = False, True, True, False
    return await cmd_run(a)


async def cmd_record(a) -> int:
    from utils.radio import kiwi
    from utils.radio.fetch import FeedError
    out = Path("recordings")
    for r in kiwi.choose(await kiwi.directory(), a.khz, a.region, n=4):
        try:
            wavs = await kiwi.record(r, a.khz, a.mode, a.seconds, out, label=f"{a.khz:g}")
        except FeedError as e:
            _say(f"{r.location or r.host}: {e}; trying the next receiver")
            continue
        for w in wavs:
            _say(f"{w}  ({r.location or r.host})")
        return 0
    _say(f"no free receiver in region {a.region!r} delivered {a.khz:g} kHz")
    return 1


async def cmd_uvb76(a) -> int:
    import json
    from utils.radio import watch
    out = await watch.sample_uvb76({"khz": 4625.0, "region": "ne", "seconds": a.seconds})
    if not out:
        _say("no receiver gave readings")
        return 1
    d = json.loads(out.read_text())
    _say(f"{out}: {d['buzz'].get('state')} (period {d['buzz'].get('period_s')} s) from {d['receiver_location']}; "
         f"clip {d['clip'] and 'memory/radio/uvb76/' + d['clip']} from {d['clip_receiver']}")
    return 0


def cmd_notebook(a) -> int:
    import runpy
    sys.argv = ["band_notebook.py", "--write"]
    runpy.run_path("tools/maintenance/band_notebook.py", run_name="__main__")
    return 0


def cmd_status(a) -> int:
    import json
    import sqlite3
    db = Path("memory/radio/local_ledger.sqlite3")
    if db.exists():
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        rows = con.execute("select kind, count(*) from events group by kind order by 2 desc").fetchall()
        _say("ledger: " + ", ".join(f"{n} {k}" for k, n in rows))
        for f, v, h in con.execute("select freq_hz, voice, hits from channels where voice > 0 order by voice desc limit 8"):
            _say(f"  {f / 1e6:.4f} MHz  voice {v}  heard {h}")
    else:
        _say("ledger: empty (the watch has not run yet)")
    health = Path("memory/radio/kiwi_health.json")
    if health.exists():
        h = json.loads(health.read_text())
        _say(f"KiwiSDR receivers judged: {len(h.get('hosts', {}))}; muted frequencies benched: "
             + (", ".join(h.get("muted", {})) or "none"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="kaiarx", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="dashboard + nightly watch + scheduled listens")
    r.add_argument("--window", action="store_true", help="open the dashboard as an app window")
    r.add_argument("--no-local", action="store_true", help="no RTL-SDR watch")
    r.add_argument("--no-web", action="store_true", help="no KiwiSDR listens or feeds")
    r.add_argument("--no-dashboard", action="store_true")
    d = sub.add_parser("dash", help="the receiver dashboard")
    d.add_argument("--no-window", action="store_true", help="serve only; open the address yourself")
    rec = sub.add_parser("record", help="one KiwiSDR recording")
    rec.add_argument("khz", type=float)
    rec.add_argument("mode", choices=("usb", "lsb", "am", "cw", "nbfm"))
    rec.add_argument("seconds", type=float)
    rec.add_argument("--region", default="na", help="na, eu or ne (kiwi.REGIONS)")
    u = sub.add_parser("uvb76", help="one UVB-76 sample")
    u.add_argument("--seconds", type=float, default=120)
    sub.add_parser("notebook", help="rewrite the band notebook")
    sub.add_parser("status", help="ledger and receiver health")
    a = ap.parse_args()
    fn = {"run": cmd_run, "dash": cmd_dash, "record": cmd_record, "uvb76": cmd_uvb76,
          "notebook": cmd_notebook, "status": cmd_status}[a.cmd]
    import inspect
    return asyncio.run(fn(a)) if inspect.iscoroutinefunction(fn) else fn(a)


if __name__ == "__main__":
    sys.exit(main())
