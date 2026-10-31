"""Set the process up the way Kaiacord's shared modules expect. Import it first.

STANDALONE-ONLY FILE. The shared code uses paths relative to the project root
(memory/, logs/, assets/, config/), so the working directory becomes the root; the
log goes to logs/<name>.log unless KAIACORD_LOG_FILE says otherwise; and when
discord.py is not installed, standalone/shims/ (a stand-in for the few names the
shared code imports) goes on sys.path.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = ROOT.name.lower() or "kaia"


def setup(log_name: str | None = None) -> Path:
    os.chdir(ROOT)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    if importlib.util.find_spec("discord") is None:
        shims = str(ROOT / "standalone" / "shims")
        if shims not in sys.path:
            sys.path.insert(1, shims)
    (ROOT / "logs").mkdir(exist_ok=True)
    os.environ.setdefault("KAIACORD_LOG_FILE", f"logs/{log_name or NAME}.log")
    # Kaiacord re-execs itself into its venv; nothing here does.
    os.environ.setdefault("KAIA_NO_REEXEC", "1")
    return ROOT


setup()
