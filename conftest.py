"""Standalone test setup (STANDALONE-ONLY FILE).

The shared tests in tools/tests/ come from Kaiacord unchanged. A few test something
that lives only in Kaiacord (the Discord panel, the morning post); they fail here
with ModuleNotFoundError for a Kaiacord module this project does not carry, and are
reported as skipped with that module's name instead. Any other failure fails.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
if importlib.util.find_spec("discord") is None:
    sys.path.insert(1, str(ROOT / "standalone" / "shims"))
os.environ.setdefault("KAIA_NO_REEXEC", "1")


def _kaiacord_only(exc: BaseException) -> str | None:
    """The Kaiacord module a failure is missing, or None for a real failure."""
    import re
    while exc is not None:
        if isinstance(exc, ModuleNotFoundError) and exc.name and exc.name.split(".")[0] == "utils":
            return exc.name
        # `from utils.radio import overnight` when the package has no such file
        hit = re.match(r"cannot import name '(\w+)' from '(utils(?:\.\w+)*)'", str(exc)) \
            if isinstance(exc, ImportError) else None
        if hit:
            mod = f"{hit[2]}.{hit[1]}"
            path = ROOT.joinpath(*mod.split("."))
            if not path.with_suffix(".py").exists() and not (path / "__init__.py").exists():
                return mod
        exc = exc.__cause__ or exc.__context__
    return None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    outcome = yield
    if outcome.excinfo:
        missing = _kaiacord_only(outcome.excinfo[1])
        if missing:
            outcome.force_exception(pytest.skip.Exception(f"Kaiacord-only: needs {missing}", _use_item_location=True))
