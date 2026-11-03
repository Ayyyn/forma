"""Resume paid reasoning from retained receipts; replay native tools locally.

Replayed model decisions are provenance, never fresh model responses or charges.
Every tool is rerun under the currently loaded code and current asset bytes.
"""

import base64
from copy import deepcopy
import json
import re

from . import workspace_agent as wa


def restore(session, source_id, selection, log, depth=0):
    if depth >= 8:
        raise ValueError("Checkpoint ancestry exceeds eight continuations")
    if not isinstance(source_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,80}", source_id
    ):
        raise ValueError("Invalid checkpoint ID")
    folder = wa.RUNS / source_id
    prior = json.loads((folder / "proposal.json").read_text(encoding="utf-8"))
    if prior.get("status") != "incomplete":
        raise ValueError("Only an incomplete design run can be resumed")
    events = [
        json.loads(line)
        for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    requests = [e for e in events if e.get("kind") == "reservation"]
    if not requests:
        raise ValueError("Checkpoint has no retained model request")
    first = requests[0]["request"]["messages"]
    context = json.loads(
        next(
            m["content"]
            for m in first
            if m["role"] == "user"
            and isinstance(m["content"], str)
            and '"original_instruction"' in m["content"]
        )
    )
    clean_selection = lambda value: {
        k: v for k, v in (value or {}).items() if v not in (None, [], {})
    }
    if (
        context["original_instruction"] != session.instruction
        or context["project"]
        != wa._model_document(session.candidates["base"]["document"])
        or clean_selection(context.get("selection")) != clean_selection(selection)
    ):
        raise ValueError(
            "Checkpoint belongs to a different source, instruction or selection; request a new design"
        )
    replayed = getattr(session, "checkpoint_results", {})
    last_render = None
    # A continued checkpoint can itself be continued without charging for or
    # pretending to regenerate the model decisions in its ancestors.
    ancestor = (prior.get("continuation") or {}).get("source_run_id")
    if ancestor:
        restore(session, ancestor, selection, log, depth + 1)
        replayed = session.checkpoint_results
        last_render = getattr(session, "checkpoint_last_render", None)
    for event in events:
        if event.get("kind") != "tool":
            continue
        result = session.call(event["tool"], event["arguments"])
        if event["tool"] == "draft_candidate" and event.get("result", {}).get(
            "candidate_id"
        ) != result.get("candidate_id"):
            raise ValueError(
                "Candidate identity changed during replay; start a new proposal instead of silently remapping bodies"
            )
        replayed[event["call_id"]] = result
        log(
            {
                "kind": "tool_replay",
                "source_run_id": source_id,
                "source_call_id": event["call_id"],
                **session.events[-1],
                "budget_charge_usd": 0,
            }
        )
        if event["tool"] == "render_views" and result.get("ok"):
            last_render = event["arguments"]["candidate_id"]
    last_request = requests[-1]
    history = deepcopy(last_request["request"]["messages"])
    for message in history:
        if message["role"] == "tool" and message.get("tool_call_id") in replayed:
            message["content"] = json.dumps(
                replayed[message["tool_call_id"]], ensure_ascii=False, allow_nan=False
            )
        if isinstance(message.get("content"), list):
            message["content"] = [
                (
                    {
                        "type": "text",
                        "text": "[Previous image retained in checkpoint; current native render follows.]",
                    }
                    if part.get("type") == "image_url"
                    else part
                )
                for part in message["content"]
            ]
    history = [
        m
        for m in history
        if not (
            m["role"] == "user"
            and isinstance(m.get("content"), str)
            and m["content"].startswith("Current stage: concept decision only.")
        )
    ]
    index = max(i for i, e in enumerate(events) if e.get("kind") == "reservation")
    for event in events[index + 1 :]:
        if (
            event.get("kind") == "response"
            and event.get("transport", {}).get("http_status") == 200
        ):
            message = event.get("assistant_message", {})
            if message.get("content") or message.get("tool_calls"):
                history.append(deepcopy(message))
        elif event.get("kind") == "tool":
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": event["call_id"],
                    "content": json.dumps(
                        replayed[event["call_id"]], ensure_ascii=False, allow_nan=False
                    ),
                }
            )
        elif event.get("kind") == "tool_protocol_error":
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": event["call_id"],
                    "content": json.dumps({"ok": False, "error": event["error"]}),
                }
            )
    pending = []
    if last_render:
        report = session.reports[last_render]["visual"]
        image = (session.folder / report["artifact"]).read_bytes()
        history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Current locally revalidated CAD views for "
                        + last_render,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + base64.b64encode(image).decode()
                        },
                    },
                ],
            }
        )
        pending.append(last_render)
    history.append(
        {
            "role": "user",
            "content": "Continue the same design from this checkpoint. Prior tool actions were replayed locally under current tools/assets, not new model calls; inspect the updated results. Keep unresolved requirements. Do not rebuild unchanged work. If the current candidate passes the required gates, select it with finish_design after reviewing the current image.",
        }
    )
    provenance = {
        "source_run_id": source_id,
        "source_response_ids": prior.get("response_ids", []),
        "replayed_tools": len(replayed),
        "scope": "Retained model actions revalidated locally; fresh response IDs/cost count only new requests",
    }
    session.checkpoint_results = replayed
    session.checkpoint_last_render = last_render
    return history, pending, provenance
