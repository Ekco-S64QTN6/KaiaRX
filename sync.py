#!/usr/bin/env python3
"""Keep this project's shared files in step with Kaiacord, the project they come from.

Shared files live at the same relative path here and in Kaiacord (`utils/radio/scanner.py`
is `utils/radio/scanner.py` in both) and are kept byte-identical. `sync.json` lists them;
`sync.lock.json` records the hash each had when the two sides last matched, which is
how a change is told apart from the other side's change:

    python3 sync.py status            what differs, and on which side
    python3 sync.py pull              Kaiacord -> here   (files changed only in Kaiacord)
    python3 sync.py push              here -> Kaiacord   (files changed only here)
    python3 sync.py diff PATH         unified diff of one shared file, here vs Kaiacord
    python3 sync.py pull --force PATH take Kaiacord's copy of a conflicting file
    python3 sync.py push --force PATH send this copy of a conflicting file

A file changed on both sides since the last sync is a conflict: nothing is copied until
it is merged by hand (edit one side to match, then `pull` or `push` it with --force).
Kaiacord is found at `upstream` in sync.json, or $KAIACORD_DIR. Nothing here commits:
after a push, run Kaiacord's tests and commit there.
"""
from __future__ import annotations

import argparse
import difflib
import fnmatch
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "sync.json"
LOCK = HERE / "sync.lock.json"


def _load() -> tuple[dict, dict, Path]:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    up = Path(os.environ.get("KAIACORD_DIR") or (HERE / m["upstream"])).resolve()
    if not (up / "Kaiacord.py").is_file():
        sys.exit(f"Kaiacord not found at {up} (set KAIACORD_DIR or 'upstream' in sync.json)")
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    return m, lock, up


def _sha(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def _expand(m: dict, root: Path) -> set[str]:
    """The shared paths that exist under `root`: plain paths and globs, minus `exclude`."""
    out = set()
    for pat in m["shared"]:
        if any(c in pat for c in "*?["):
            out |= {str(p.relative_to(root)) for p in root.glob(pat) if p.is_file()}
        elif (root / pat).is_file():
            out.add(pat)
    skip = m.get("exclude", [])
    return {p for p in out if "__pycache__" not in p and not any(fnmatch.fnmatch(p, x) for x in skip)}


def _states(m: dict, lock: dict, up: Path) -> dict[str, str]:
    """path -> same | local | upstream | conflict | new-upstream | new-local | gone-upstream | gone-local"""
    paths = _expand(m, HERE) | _expand(m, up) | set(lock)
    out = {}
    for p in sorted(paths):
        here, there, base = _sha(HERE / p), _sha(up / p), lock.get(p)
        if here == there:
            out[p] = "same" if here else "gone"
        elif base is None:
            out[p] = "new-upstream" if here is None else "new-local" if there is None else "conflict"
        elif here is None:
            out[p] = "gone-local"
        elif there is None:
            out[p] = "gone-upstream"
        elif here == base:
            out[p] = "upstream"
        elif there == base:
            out[p] = "local"
        else:
            out[p] = "conflict"
    return out


def _copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _save_lock(lock: dict) -> None:
    LOCK.write_text(json.dumps(dict(sorted(lock.items())), indent=1) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("status", "pull", "push", "diff"))
    ap.add_argument("paths", nargs="*", help="limit to these shared paths")
    ap.add_argument("--force", action="store_true", help="resolve the named conflicts in this direction")
    a = ap.parse_args()
    m, lock, up = _load()
    states = _states(m, lock, up)
    if a.paths:
        states = {p: s for p, s in states.items() if p in a.paths}
        if not states:
            sys.exit(f"not shared paths: {' '.join(a.paths)}")

    if a.command == "status":
        changed = {p: s for p, s in states.items() if s not in ("same", "gone")}
        for p, s in changed.items():
            print(f"{s:14} {p}")
        print(f"{len(states) - len(changed)} shared files identical, {len(changed)} differ  (Kaiacord: {up})")
        return 1 if any(s == "conflict" for s in changed.values()) else 0

    if a.command == "diff":
        for p in states:
            here = (HERE / p).read_text(encoding="utf-8", errors="replace").splitlines(True) if (HERE / p).exists() else []
            there = (up / p).read_text(encoding="utf-8", errors="replace").splitlines(True) if (up / p).exists() else []
            sys.stdout.writelines(difflib.unified_diff(there, here, f"Kaiacord/{p}", f"here/{p}"))
        return 0

    pull = a.command == "pull"
    src, dst = (up, HERE) if pull else (HERE, up)
    mine = ("upstream", "new-upstream") if pull else ("local", "new-local")
    copied, conflicts, removed = [], [], []
    for p, s in states.items():
        if s in mine or (a.force and a.paths and s in ("conflict", "upstream", "local", "new-upstream", "new-local")):
            if (src / p).is_file():
                _copy(src / p, dst / p)
                lock[p] = _sha(src / p)
                copied.append(p)
        elif s == ("gone-upstream" if pull else "gone-local"):
            # Deleted on the source side and unchanged here since the last sync: delete here too.
            # A push never deletes in Kaiacord unless the path is named with --force.
            if not pull and not (a.force and p in a.paths):
                print(f"skipped  {p}  (deleted here; to delete it in Kaiacord too: push --force {p})")
            elif _sha(dst / p) == lock.get(p):
                (dst / p).unlink()
                lock.pop(p, None)
                removed.append(p)
            else:
                conflicts.append(p)
        elif s == "same":
            lock[p] = _sha(src / p)
        elif s == "conflict":
            conflicts.append(p)
    _save_lock(lock)
    if pull:
        # Read-only references: Kaiacord's rules for this code, kept current on every pull.
        for src_rel, dst_rel in m.get("reference", {}).items():
            if (up / src_rel).is_file():
                _copy(up / src_rel, HERE / dst_rel)
                print(f"reference {dst_rel}  (from Kaiacord/{src_rel}; do not edit here)")
    arrow = "Kaiacord -> here" if pull else "here -> Kaiacord"
    for p in copied:
        print(f"copied   {p}")
    for p in removed:
        print(f"removed  {p}")
    for p in conflicts:
        print(f"CONFLICT {p}  (changed on both sides: merge by hand, then {a.command} --force {p})")
    print(f"{arrow}: {len(copied)} copied, {len(removed)} removed, {len(conflicts)} conflicts")
    if not pull and copied:
        print("Now run Kaiacord's tests there and commit:  venv/bin/python3 -m pytest -q -m \"not ollama and not gpu and not slow\"")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
