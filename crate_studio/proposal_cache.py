"""Versioned exact proposal reuse and concurrent identical-call coalescing."""

from contextlib import contextmanager
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import threading

from .workspace_cache import asset_identity

_guard = threading.Lock()
_inflight = {}


def identity(document, instruction, selection, settings, asset_loader):
    directory = Path(__file__).parent
    versions = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in [
            "workspace_agent.py",
            "workspace_geometry.py",
            "workspace_cache.py",
            "workspace_requirements.py",
            "workspace_workflow.py",
            "engine.py",
            "proposal_cache.py",
        ]
    }
    versions["cadquery"] = version("cadquery")
    versions["cadquery-ocp"] = version("cadquery-ocp")
    encoded = json.dumps(
        {
            "document": document,
            "instruction": instruction,
            "selection": selection or {},
            "settings": settings,
            "assets": asset_identity(document, asset_loader),
            "versions": versions,
        },
        sort_keys=True,
        allow_nan=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@contextmanager
def single_flight(key):
    with _guard:
        entry = _inflight.setdefault(key, [threading.RLock(), 0])
        entry[1] += 1
    try:
        with entry[0]:
            yield
    finally:
        with _guard:
            entry[1] -= 1
            if not entry[1]:
                del _inflight[key]


def read(folder, key):
    path = folder / "_proposal_cache" / (key + ".json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["key"] == key and isinstance(data["plan"], dict):
            return data
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def write(folder, key, value):
    path = folder / "_proposal_cache" / (key + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"key": key, **value}, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    temporary.replace(path)
