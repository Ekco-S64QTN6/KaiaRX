"""KaiaRX's own checks (STANDALONE-ONLY FILE): the stand-ins and the wiring around the shared code."""
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _shared() -> set[str]:
    m = json.loads((ROOT / "sync.json").read_text())
    out = set()
    for pat in m["shared"]:
        out |= {str(p.relative_to(ROOT)) for p in ROOT.glob(pat) if p.is_file()} if any(c in pat for c in "*?[") \
            else ({pat} if (ROOT / pat).is_file() else set())
    return {p for p in out if p not in m.get("exclude", [])}


def test_the_discord_stand_in_provides_every_name_the_shared_code_uses():
    """A shared module that starts using more of discord.py has to fail here, not at runtime."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("discord_shim", ROOT / "standalone/shims/discord/__init__.py")
    shim = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim)
    used = set()
    for rel in _shared():
        if not rel.endswith(".py") or "/tests/" in rel:
            continue
        for node in ast.walk(ast.parse((ROOT / rel).read_text())):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "discord":
                used.add(node.attr)
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute) \
                    and isinstance(node.value.value, ast.Name) and node.value.value.id == "discord":
                used.add(f"{node.value.attr}.{node.attr}")
    # Names only Discord features use (the bot's voice, embeds…) are allowed to be missing:
    # those features cannot run standalone. Everything else must exist.
    discord_only = {"utils", "Embed", "Color", "Colour", "ui", "ButtonStyle", "Interaction", "File",
                    "Member", "Guild", "TextChannel", "Message", "Intents", "Client", "app_commands"}
    missing = []
    for name in sorted(used):
        head = name.split(".")[0]
        if head in discord_only:
            continue
        obj = shim
        try:
            for part in name.split("."):
                obj = getattr(obj, part)
        except AttributeError:
            missing.append(name)
    assert not missing, f"standalone/shims/discord lacks {missing}"


def test_the_entry_point_starts_and_lists_its_commands():
    out = subprocess.run([sys.executable, str(ROOT / "kaiarx.py"), "--help"], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0 and "record" in out.stdout and "dash" in out.stdout


def test_config_reads_kaiacord_keys_and_local_overrides(tmp_path, monkeypatch):
    from utils.infrastructure.system import yaml_config as yc
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "default_config.yaml").write_text("radio:\n  local:\n    hours: '00:00-06:00'\n    gain: 40\n")
    (tmp_path / "config" / "local.yaml").write_text("radio:\n  local:\n    gain: 28\n")
    monkeypatch.setattr(yc, "ROOT", tmp_path)
    c = yc.YAMLConfig()
    assert c.get("radio.local.gain") == 28 and c.get("radio.local.hours") == "00:00-06:00"
    assert c.get("radio.nope", "x") == "x"


def test_shared_files_match_the_lock():
    """Shared files differ from the lock only through an edit not yet pushed or pulled —
    which `sync.py status` reports. This just checks the lock covers every shared file."""
    lock = json.loads((ROOT / "sync.lock.json").read_text())
    assert _shared() <= set(lock), sorted(_shared() - set(lock))
