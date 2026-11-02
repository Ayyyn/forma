"""Refresh internal Forma budget notes from local receipts; no API or credentials.

The application guard retains reservations. It is deliberately different from
receipt cost estimates and from the provider's actual invoice/credit balance.
"""

import ast
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "docs/FORMA_ENGINEERING_LOG.md"
SNAPSHOT = ROOT / "docs/FORMA_BUDGET_SNAPSHOT.json"
START = "<!-- FORMA_BUDGET_START -->"
END = "<!-- FORMA_BUDGET_END -->"


def dollars(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid amount: {label}")
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError(f"Invalid amount: {label}")
    return number


def amount(value):
    return float(value.quantize(Decimal("0.00000001")))


def snapshot():
    cap = None
    for node in ast.parse(
        (ROOT / "crate_studio/agent.py").read_text(encoding="utf8")
    ).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(n, ast.Name) and n.id == "CAP_USD" for n in node.targets
        ):
            cap = dollars(ast.literal_eval(node.value), "CAP_USD")
    if cap is None:
        raise ValueError("Application cap not found")
    groups = {
        name: {
            "responses": 0,
            "estimates": Decimal(0),
            "guard": Decimal(0),
            "reservations": Decimal(0),
            "missing_estimates": 0,
        }
        for name in (
            "Earlier Forma work",
            "Full17 Forma",
            "Full17 Build123D",
            "Diagnostic development",
        )
    }
    ledgers = []
    counts = Counter()
    models = Counter()
    for relative in ("output/forma/agent", "output/forma/studio/agent"):
        paths = sorted((ROOT / relative).glob("*/events.jsonl"))
        if not paths:
            raise FileNotFoundError(
                f"Receipt ledger unavailable: {relative}; existing budget snapshot left unchanged"
            )
        for path in paths:
            data = path.read_bytes()
            ledgers.append(
                (path.relative_to(ROOT).as_posix(), hashlib.sha256(data).hexdigest())
            )
            run_id = path.parent.name
            key = (
                "Diagnostic development"
                if run_id.startswith("diagnostic-")
                else (
                    "Full17 Forma"
                    if run_id.startswith("full17-forma-")
                    else (
                        "Full17 Build123D"
                        if run_id.startswith("full17-build123d-")
                        else "Earlier Forma work"
                    )
                )
            )
            group = groups[key]
            for index, line in enumerate(data.decode("utf-8").splitlines(), 1):
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError(f"Invalid receipt object: {path.name}:{index}")
                kind = event.get("kind", "legacy_response")
                counts[kind] += 1
                charge = dollars(event.get("budget_charge_usd", 0), "budget charge")
                group["guard"] += charge
                if kind == "reservation":
                    group["reservations"] += charge
                if kind == "response" or (
                    kind == "legacy_response" and "transport" in event
                ):
                    group["responses"] += 1
                    models[str(event.get("model", "unrecorded"))] += 1
                    if "estimated_cost_usd" in event:
                        group["estimates"] += dollars(
                            event["estimated_cost_usd"], "response estimate"
                        )
                    else:
                        group["missing_estimates"] += 1
    total_guard = sum(g["guard"] for g in groups.values())
    ist = timezone(timedelta(hours=5, minutes=30))
    return {
        "as_of_ist": datetime.now(timezone.utc)
        .astimezone(ist)
        .isoformat(timespec="seconds"),
        "scope": "Local Forma application ledgers only; earlier non-Forma prototypes and provider account balances are outside this snapshot.",
        "approved_application_cap_usd": amount(cap),
        "conservative_guard_usd": amount(total_guard),
        "guard_headroom_usd": amount(cap - total_guard) if cap >= total_guard else None,
        "cap_exceeded": total_guard > cap,
        "recorded_response_estimates_usd": amount(
            sum(g["estimates"] for g in groups.values())
        ),
        "response_count": sum(g["responses"] for g in groups.values()),
        "responses_missing_explicit_estimate": sum(
            g["missing_estimates"] for g in groups.values()
        ),
        "provider_billing_verified": False,
        "provider_remaining_credits_usd": None,
        "groups": {
            name: {
                k: amount(v) if isinstance(v, Decimal) else v for k, v in group.items()
            }
            for name, group in groups.items()
        },
        "event_counts": dict(counts),
        "response_models": dict(models),
        "ledger_file_count": len(ledgers),
        "ledger_manifest_sha256": hashlib.sha256(
            json.dumps(ledgers, separators=(",", ":")).encode()
        ).hexdigest(),
        "accounting": "Guard sums persisted budget_charge_usd, including reservations which are not released. Recorded estimates sum response estimated_cost_usd only; historical pricing/estimation policies differ. Neither is a provider invoice. Full17 groups include every restored second attempt.",
    }


def main():
    text = LOG.read_text(encoding="utf8")
    if (
        text.count(START) != 1
        or text.count(END) != 1
        or text.index(START) > text.index(END)
    ):
        raise ValueError("Budget markers must appear once, in order")
    data = snapshot()
    lines = [
        f"As of **{data['as_of_ist']} (IST)**. Generated from the two local Forma receipt ledgers; this refresh makes no model call.",
        "",
        "| Budget measure | USD | Meaning |",
        "|---|---:|---|",
        f"| Approved application cap | ${data['approved_application_cap_usd']:.2f} | Read from the app; approval history is recorded above |",
        f"| Conservative guard charge | ${data['conservative_guard_usd']:.6f} | Persisted reservations plus charge entries; includes earlier Forma experiments |",
        f"| Guard headroom | {'Exceeded' if data['guard_headroom_usd'] is None else '$'+format(data['guard_headroom_usd'], '.6f')} | Application permission to reserve more; not remaining provider credits |",
        f"| Sum of recorded response estimates | ${data['recorded_response_estimates_usd']:.7f} | {data['response_count']} responses; {data['responses_missing_explicit_estimate']} lack an explicit estimate; historical estimation policies differ |",
        "| Provider invoice and remaining credits | Unknown | Not verified against Meta, Baseten or Modal billing |",
        "",
        "| Nonoverlapping ledger group | Responses | Recorded estimates USD | Guard charge USD |",
        "|---|---:|---:|---:|",
    ]
    for name, group in data["groups"].items():
        lines.append(
            f"| {name} | {group['responses']} | ${group['estimates']:.7f} | ${group['guard']:.6f} |"
        )
    full_responses = sum(
        data["groups"][key]["responses"] for key in ("Full17 Forma", "Full17 Build123D")
    )
    full_estimate = sum(
        data["groups"][key]["estimates"] for key in ("Full17 Forma", "Full17 Build123D")
    )
    lines += [
        "",
        f"The sum of estimates is a sum of recorded estimates under historical policies, not a consistently repriced lifetime spend. The full17 ledger groups contain {full_responses} responses totaling **${full_estimate:.7f} estimated**. Archived copies and kernel replays are excluded from new-call counting. The shared guard is application-wide, not the cost of the Batman design alone.",
        "",
        "Refresh: `python -m research.update_forma_engineering_budget`. Machine-readable snapshot: [FORMA_BUDGET_SNAPSHOT.json](FORMA_BUDGET_SNAPSHOT.json). The refresh refuses missing or malformed ledgers, preserving the previous snapshot rather than inventing a zero balance.",
    ]
    updated = (
        text[: text.index(START) + len(START)]
        + "\n\n"
        + "\n".join(lines)
        + "\n\n"
        + text[text.index(END) :]
    )
    SNAPSHOT.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf8",
    )
    LOG.write_text(updated, encoding="utf8")
    print(
        json.dumps(
            {
                k: data[k]
                for k in (
                    "as_of_ist",
                    "conservative_guard_usd",
                    "guard_headroom_usd",
                    "response_count",
                    "recorded_response_estimates_usd",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
