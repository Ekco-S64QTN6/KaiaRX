"""Standalone configuration: config/default_config.yaml, overridden by config/local.yaml.

STANDALONE-ONLY FILE (not shared with Kaiacord). Kaiacord's yaml_config.py loads the
same way but refuses to start without a Discord token and a Gemini key; the shared
code here only ever calls `config.get("dotted.path", default)`, so this keeps that
interface and nothing else. Keys are Kaiacord's (`radio.local.hours` …), so a value
that works there works here.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must hold a mapping at the top level")
    return data


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


class YAMLConfig:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self._data = deep_merge(_read(ROOT / "config" / "default_config.yaml"),
                                _read(ROOT / "config" / "local.yaml"))

    def get(self, path: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    get_path = get

    def set(self, path: str, value: Any) -> None:
        """Override one value for this run (command-line flags). Not in Kaiacord's
        interface; only standalone-only code calls it."""
        node = self._data
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value


config = YAMLConfig()
