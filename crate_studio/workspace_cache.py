"""Exact in-process CAD reuse. Never cache by approximate or semantic similarity.

Cached BREP objects are read-only, matching Studio's existing build-cache contract.
Imported files are keyed by bytes, not mutable paths or loader identity.
"""

from collections import OrderedDict, namedtuple
import hashlib
import json
from pathlib import Path
import threading

from .workspace_geometry import build_document
from .viewport_measurements import body_measurements

VERSION = hashlib.sha256(
    Path(__file__).with_name("workspace_geometry.py").read_bytes()
    + Path(__file__).with_name("mechanical_features.py").read_bytes()
    + Path(__file__).with_name("mechanical_validation.py").read_bytes()
    + Path(__file__).with_name("folding.py").read_bytes()
).hexdigest()
_lock = threading.RLock()
_values = OrderedDict()
_hits = _misses = 0
Info = namedtuple("CacheInfo", "hits misses maxsize currsize")
MAXSIZE = 20


def asset_identity(document, loader):
    ids = sorted(
        {
            f.get("params", {}).get("asset_id")
            for f in document.get("features", [])
            if f.get("type") == "import_step"
        }
    )
    return [
        (ident, hashlib.sha256(Path(loader(ident)).read_bytes()).hexdigest())
        for ident in ids
    ]


def _build_identity(document, asset_loader):
    assets = asset_identity(document, asset_loader)
    return json.dumps(
        [
            VERSION,
            document["features"],
            document.get("metadata", {}).get("gear_targets", []),
            assets,
        ],
        sort_keys=True,
        allow_nan=False,
    )


def lookup_build(document, asset_loader=None):
    """Read an immutable owned build without starting any native operation."""
    global _hits
    try:
        key = _build_identity(document, asset_loader)
    except (ValueError, TypeError, KeyError, OSError):
        return None
    with _lock:
        result = _values.get(key)
        if result is not None:
            _hits += 1
            _values.move_to_end(key)
        return result


def cached_build(document, asset_loader=None):
    global _hits, _misses
    try:
        key = _build_identity(document, asset_loader)
    except (ValueError, TypeError, KeyError, OSError):
        return _measured_build(document, asset_loader)
    with _lock:
        if key in _values:
            _hits += 1
            _values.move_to_end(key)
            return _values[key]
        _misses += 1
        result = _measured_build(document, asset_loader)
        if result["checks"]["passed"] or not document["features"]:
            _values[key] = result
            while len(_values) > MAXSIZE:
                _values.popitem(last=False)
        return result


def _measured_build(document, asset_loader):
    # Derive reference dimensions once with the native build, while its caller
    # owns the CAD lock. Warm snapshots copy only plain data, never query BREP.
    result = build_document(document, asset_loader)
    result["body_measurements"] = body_measurements(result["parts"])
    return result


def cache_clear():
    global _hits, _misses
    with _lock:
        _values.clear()
        _hits = _misses = 0


def cache_info():
    with _lock:
        return Info(_hits, _misses, MAXSIZE, len(_values))


def identity_for_build(result):
    """Identity only for a currently owned, exact native build; never infer one.

    Direct build_document callers bypass downstream reuse. Assets and loaded
    geometry code are already included in the owned cache key.
    """
    with _lock:
        for key, value in _values.items():
            if value is result:
                return hashlib.sha256(key.encode()).hexdigest()
    return None
