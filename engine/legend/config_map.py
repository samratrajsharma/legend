"""Configuration surface — the runtime knobs static code parsing misses: config files
(yaml/toml/ini/cfg), argparse CLI flags, and UPPER_CASE settings. Especially useful for ML
repos, where behaviour is driven by configs and hyperparameters."""
from __future__ import annotations
import os
import re

_KEY = re.compile(r"(?m)^[ \t]*([A-Za-z_][\w-]*)\s*[:=]")
_SECTION = re.compile(r"(?m)^\[([^\]]+)\]")
_ARG = re.compile(r"""add_argument\(\s*["'](--?[\w-]+)["']""")
_UPPER = re.compile(r"(?m)^([A-Z][A-Z0-9_]{2,})\s*=")
_JSON_KEY = re.compile(r'"([A-Za-z_][\w-]*)"\s*:')


def config_surface(idx):
    out = []
    for p in idx.parsed_files:
        txt = p.text or ""
        ext = os.path.splitext(p.file)[1].lower()
        if ext in (".yaml", ".yml"):
            keys = sorted(set(_KEY.findall(txt)))[:40]
            if keys:
                out.append({"source": p.file, "kind": "yaml", "items": keys})
        elif ext in (".toml", ".ini", ".cfg"):
            items = sorted(set(_KEY.findall(txt)) | set(_SECTION.findall(txt)))[:40]
            if items:
                out.append({"source": p.file, "kind": ext.strip("."), "items": items})
        elif ext == ".json":
            keys = sorted(set(_JSON_KEY.findall(txt)))[:40]
            if keys:
                out.append({"source": p.file, "kind": "json", "items": keys})
        if p.language == "python":
            args = sorted(set(_ARG.findall(txt)))
            if args:
                out.append({"source": p.file, "kind": "cli args", "items": args[:40]})
            low = p.file.lower()
            if "config" in low or "setting" in low:
                ups = sorted(set(_UPPER.findall(txt)))
                if ups:
                    out.append({"source": p.file, "kind": "settings", "items": ups[:40]})
    return out
