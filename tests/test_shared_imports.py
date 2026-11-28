"""Every shared module imports here, without the bot.

A shared file that gains a module-level import of another Kaiacord module
breaks this repo unless that module is shared too: `dj_dashboard` importing
`record_cues` (27 Nov) failed KaiaRX's window while its suite still passed,
because no test imported `dj_dashboard`.
"""
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = [p for p in json.loads((ROOT / "sync.json").read_text())["shared"]
          if p.startswith("utils/") and p.endswith(".py") and "*" not in p]


@pytest.mark.parametrize("path", SHARED)
def test_a_shared_module_imports_here(path):
    # Failed outside the except block: conftest turns a missing module, even as
    # the context of another exception, into a Kaiacord-only skip.
    error = None
    try:
        importlib.import_module(path[:-3].replace("/", ".").removesuffix(".__init__"))
    except ImportError as e:
        error = str(e)
    if error:
        pytest.fail(f"{path} does not import here: {error} (share the module it needs, or import it lazily)")
