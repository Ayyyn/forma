"""Receipt-derived application guard, separate from provider balances/billing."""

from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import threading
import time


def money(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Invalid receipt amount")
    value = Decimal(str(value))
    if not value.is_finite() or value < 0:
        raise ValueError("Invalid receipt amount")
    return value


def ledger_summary(path):
    events = [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
    ]
    pending, by_attempt, seen = {}, defaultdict(list), set()
    settled = raw = released = Decimal(0)
    uncertain = responses = 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError("Malformed receipt object")
        charge = money(event.get("budget_charge_usd", 0))
        raw += charge
        kind = event.get("kind", "legacy_response")
        if kind == "reservation":
            ident = event.get("budget_request_id") or f"legacy:{index}"
            if ident in pending or ident in seen:
                raise ValueError("Duplicate request reservation")
            pending[ident] = charge
            by_attempt[event.get("attempt")].append(ident)
        elif kind == "response" or (kind == "legacy_response" and "transport" in event):
            responses += 1
            ident = event.get("budget_request_id")
            if ident and ident in seen:
                raise ValueError("Duplicate request settlement")
            if ident:
                seen.add(ident)
            else:
                candidates = [
                    key for key in by_attempt[event.get("attempt")] if key in pending
                ]
                # Historical receipts did not have a request ID. Never guess
                # when more than one request could match.
                ident = candidates[0] if len(candidates) == 1 else None
            reservation = pending.pop(ident, Decimal(0))
            usage = (event.get("transport") or {}).get("usage") or {}
            measured = event.get("usage_complete") is True or (
                event.get("usage_complete") is None
                and all(
                    type(usage.get(key)) is int and usage[key] >= 0
                    for key in ("prompt_tokens", "completion_tokens")
                )
            )
            estimate = event.get("estimated_cost_usd")
            if measured and estimate is not None:
                amount = money(estimate)
                released += max(Decimal(0), reservation - amount)
            else:
                amount = max(
                    reservation,
                    charge,
                    money(estimate) if estimate is not None else Decimal(0),
                )
                uncertain += 1
            settled += amount
        else:
            # Explicit historical charges remain; replay/cache/tool events are zero.
            settled += charge
    return {
        "guard": settled + sum(pending.values(), Decimal(0)),
        "settled": settled,
        "open_reservations": sum(pending.values(), Decimal(0)),
        "open_request_count": len(pending),
        "uncertain_response_count": uncertain,
        "response_count": responses,
        "historical_debits": raw,
        "released_completed_reservations": released,
    }


def usage(roots, require_roots=False):
    totals = {
        key: Decimal(0)
        for key in (
            "guard",
            "settled",
            "open_reservations",
            "historical_debits",
            "released_completed_reservations",
        )
    }
    totals.update(open_request_count=0, uncertain_response_count=0, response_count=0)
    for root in roots:
        root = Path(root)
        if require_roots and not root.is_dir():
            raise FileNotFoundError(
                "Forma receipt history is unavailable; retained budget must be restored"
            )
        for path in root.glob("*/events.jsonl"):
            row = ledger_summary(path)
            for key in totals:
                totals[key] += row[key]
    return totals


class BudgetLock:
    """Serialize the existing paid-request critical section across processes."""

    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        self.local = threading.local()

    def __enter__(self):
        self.lock.acquire()
        try:
            if not getattr(self.local, "depth", 0):
                path = Path(self.path())
                path.parent.mkdir(parents=True, exist_ok=True)
                handle = path.open("a+b")
                if not path.stat().st_size:
                    handle.write(b"0")
                    handle.flush()
                start = time.monotonic()
                while True:
                    try:
                        handle.seek(0)
                        if __import__("os").name == "nt":
                            import msvcrt

                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except OSError:
                        if time.monotonic() - start > 330:
                            handle.close()
                            raise TimeoutError(
                                "Another Forma request still owns the receipt lock"
                            )
                        time.sleep(0.05)
                self.local.handle = handle
            self.local.depth = getattr(self.local, "depth", 0) + 1
            return self
        except BaseException:
            self.lock.release()
            raise

    def __exit__(self, *args):
        self.local.depth -= 1
        try:
            if not self.local.depth:
                self.local.handle.close()  # Closing releases the OS lock.
                del self.local.handle
        finally:
            self.lock.release()
