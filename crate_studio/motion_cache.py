"""Bounded process-local exact reuse of native sampled motion reports."""

from collections import OrderedDict, namedtuple
from copy import deepcopy
import json
import threading

Info = namedtuple("Info", "hits misses entries bytes")


class ExactMotionCache:
    def __init__(self, max_entries=4, max_bytes=24 * 1024 * 1024):
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self.values = OrderedDict()
        self.lock = threading.RLock()
        self.hits = self.misses = self.bytes = 0

    def compute(self, key, calculate):
        if key is None:
            return calculate()
        # Native work stays serialized; duplicate requests wait for the first
        # result rather than computing the same trajectory twice.
        with self.lock:
            if key in self.values:
                self.hits += 1
                self.values.move_to_end(key)
                return deepcopy(self.values[key][0])
            self.misses += 1
            result = calculate()
            size = len(
                json.dumps(result, separators=(",", ":"), allow_nan=False).encode()
            )
            if size <= self.max_bytes:
                while self.values and (
                    len(self.values) >= self.max_entries
                    or self.bytes + size > self.max_bytes
                ):
                    _, (_, removed) = self.values.popitem(last=False)
                    self.bytes -= removed
                self.values[key] = (deepcopy(result), size)
                self.bytes += size
            return result

    def clear(self):
        with self.lock:
            self.values.clear()
            self.hits = self.misses = self.bytes = 0

    def info(self):
        with self.lock:
            return Info(self.hits, self.misses, len(self.values), self.bytes)


native_motion_cache = ExactMotionCache()
