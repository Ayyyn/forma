"""Resume paid reasoning from retained receipts; replay native tools locally.

Replayed model decisions are provenance, never fresh model responses or charges.
Every tool is rerun under the currently loaded code and current asset bytes.
"""

import base64
from copy import deepcopy
import json
import re

from . import workspace_agent as wa


def _canonical_project(document):
    value = wa._model_document(deepcopy(document))
    value.setdefault("metadata", {}).setdefault(
        "drawing_layout", "legacy-v1" if value.get("annotations") else "aligned-v1"
    )
    return value


def retained_context(source_id, depth=0):
    """Find original context even if a continuation failed before its first call."""
    if (
        depth >= 8
        or not isinstance(source_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", source_id)
    ):
        raise ValueError("Invalid checkpoint ancestry")
    folder = wa.RUNS / source_id
    prior = json.loads((folder / "proposal.json").read_text(encoding="utf-8"))
    if prior.get("status") != "incomplete":
        raise ValueError("Only an incomplete design run can be resumed")
    events = [
        json.loads(line)
        for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    local = next(
        (
            event.get("context")
            for event in events
            if event.get("kind") == "design_context"
        ),
        None,
    )
    if local is not None:
        return local
    for event in events:
        if event.get("kind") != "reservation":
            continue
        for message in event["request"]["messages"]:
            value = message.get("content")
            if (
                message.get("role") == "user"
                and isinstance(value, str)
                and '"original_instruction"' in value
            ):
                return json.loads(value)
    ancestor = (prior.get("continuation") or {}).get("source_run_id")
    if ancestor and not any(e.get("kind") == "tool" for e in events):
        return retained_context(ancestor, depth + 1)
    raise ValueError("Checkpoint has no original design context")


def restore(session, source_id, selection, log, depth=0, on_event=None):
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
        ancestor = (prior.get("continuation") or {}).get("source_run_id")
        if ancestor and not any(e.get("kind") == "tool" for e in events):
            history, pending, provenance = restore(
                session, ancestor, selection, log, depth + 1, on_event
            )
            return (
                history,
                pending,
                {
                    **provenance,
                    "source_run_id": source_id,
                    "recovered_request_run_id": ancestor,
                    "recovery": "Continuation failed before a model request; original ancestor revalidated",
                },
            )
        raise ValueError("Checkpoint has no retained model request")
    context = retained_context(source_id, depth)

    def clean_selection(value):
        return {k: v for k, v in (value or {}).items() if v not in (None, [], {})}

    if (
        context["original_instruction"] != session.instruction
        or _canonical_project(context["project"])
        != _canonical_project(session.candidates["base"]["document"])
        or clean_selection(context.get("selection")) != clean_selection(selection)
    ):
        raise ValueError(
            "Checkpoint belongs to a different source, instruction or selection; request a new design"
        )
    # Preserve original candidate IDs while allowing the equivalent explicit
    # drawing-layout default introduced by the document reader. Every geometric
    # and other source field still has to match before this one-field migration.
    base = session.candidates["base"]["document"]
    if "drawing_layout" not in context["project"].get(
        "metadata", {}
    ) and "drawing_layout" in base.get("metadata", {}):
        base["metadata"].pop("drawing_layout")
        log(
            {
                "kind": "checkpoint_schema_migration",
                "field": "metadata.drawing_layout",
                "detail": "Equivalent default restored to original representation for candidate identity",
                "budget_charge_usd": 0,
            }
        )
    replayed = getattr(session, "checkpoint_results", {})
    last_render = None
    floor_images = {}
    state_images = {}
    assembly_failure = None
    # A continued checkpoint can itself be continued without charging for or
    # pretending to regenerate the model decisions in its ancestors.
    ancestor = (prior.get("continuation") or {}).get("source_run_id")
    if ancestor:
        restore(session, ancestor, selection, log, depth + 1, on_event)
        replayed = session.checkpoint_results
        last_render = getattr(session, "checkpoint_last_render", None)
        floor_images = getattr(session, "checkpoint_floor_images", {})
        state_images = getattr(session, "checkpoint_state_images", {})
        assembly_failure = getattr(session, "checkpoint_assembly_failure", None)
    tool_events = [e for e in events if e.get("kind") == "tool"]
    replay_index = 0
    for event in events:
        if event.get("kind") != "tool":
            continue
        replay_index += 1
        if on_event:
            on_event(
                "revalidation",
                f"Rechecking retained tools {replay_index}/{len(tool_events)} · {event['tool']} · no model call",
            )
        result = session.call(event["tool"], event["arguments"])
        if event["tool"] in ("draft_candidate", "insert_component") and event.get(
            "result", {}
        ).get("candidate_id") != result.get("candidate_id"):
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
        if (
            event["tool"] == "check_floor"
            and result.get("ok")
            and result.get("image_artifact")
        ):
            floor_images[
                (event["arguments"]["candidate_id"], result.get("state_name"))
            ] = result
        if event["tool"] == "render_state" and result.get("ok"):
            state_images[(event["arguments"]["candidate_id"], result["state_name"])] = (
                result
            )
        if event["tool"] == "check_assembly" and result.get("ok"):
            assembly_failure = (
                (event["arguments"]["candidate_id"], result)
                if result.get("failure_image_artifact")
                else None
            )
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
    diagnostics = []
    for result in list(floor_images.values())[-4:]:
        image = (session.folder / result["image_artifact"]).read_bytes()
        diagnostics.extend(
            [
                {
                    "type": "text",
                    "text": "Current revalidated support diagnostic for "
                    + str(result.get("state_name") or "static pose"),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(image).decode()
                    },
                },
            ]
        )
    if diagnostics:
        history.append({"role": "user", "content": diagnostics})
    state_views = []
    latest_candidate = next(reversed(state_images))[0] if state_images else None
    for (ident, name), result in state_images.items():
        if ident != latest_candidate:
            continue
        image = (session.folder / result["artifact"]).read_bytes()
        state_views.extend(
            [
                {
                    "type": "text",
                    "text": "Current native named-state views for "
                    + ident
                    + " / "
                    + name,
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/png;base64,"
                        + base64.b64encode(image).decode()
                    },
                },
            ]
        )
        pending.append(
            {"candidate_id": ident, "report_key": result["visual_report_key"]}
        )
    if state_views:
        history.append({"role": "user", "content": state_views})
    if assembly_failure:
        ident, result = assembly_failure
        image = (session.folder / result["failure_image_artifact"]).read_bytes()
        history.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Revalidated first assembly-collision diagnostic for "
                        + ident
                        + ". Only the actual colliding pair is shown. This is a failed installation, not an accepted-design visual review.",
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
    session.checkpoint_floor_images = floor_images
    session.checkpoint_state_images = state_images
    session.checkpoint_assembly_failure = assembly_failure
    return history, pending, provenance
