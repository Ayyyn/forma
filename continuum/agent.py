"""Bounded live Meta tool loop. Public outputs only; no private reasoning persisted."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .geometry import Design, Requirements, evaluate, validate_geometry
from .search import baseline_design, search

# Reuse the already authenticated, bounded stdlib transport; no SDK dependency.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from api_preflight import load_env, request

ROOT = Path(__file__).resolve().parents[1]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_id: str = Field(min_length=10, max_length=10)
    rationale: str = Field(min_length=10, max_length=1600)


class SearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    family: str = "both"
    count: int = Field(128, ge=16, le=512)
    gamma_min: float = Field(40, ge=25, le=85)
    gamma_max: float = Field(80, ge=25, le=85)
    seed: int = Field(27, ge=0, le=10000)


def compact(candidate):
    return {"id": candidate["id"], "design": candidate["design"], "feasible": candidate["feasible"],
            "metrics": candidate["metrics"],
            "violations": [c for c in candidate["constraints"] if not c["passed"]]}


def available():
    load_env()
    return {"baseten": bool(os.environ.get("BASETEN_API_KEY")),
            "meta": bool(os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY"))}


def run_feedback_agent(requirements: Requirements, brief: str, provider="baseten"):
    load_env()
    if provider == "baseten":
        base, key, model = "https://inference.baseten.co/v1", os.environ.get("BASETEN_API_KEY"), "meta-models/muse-spark-open-1026"
    elif provider == "meta":
        base, key, model = "https://api.meta.ai/v1", os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY"), "muse-spark-1.3"
    else:
        raise ValueError("Unknown provider")
    if not key:
        raise ValueError("Selected provider key is not configured locally")
    baseline = evaluate(baseline_design(), requirements)
    pool, trace = {baseline["id"]: baseline}, []
    tools = [
        {"type": "function", "function": {"name": "evaluate_design", "description": "Evaluate an exact panel proposal against the immutable requirements. Accordion must use rows=1 and gamma_deg=90; Miura uses at least 2 rows and gamma<=85. Angles follow Schenk & Guest.", "parameters": Design.model_json_schema()}},
        {"type": "function", "function": {"name": "search_designs", "description": "Run a bounded seeded geometric search in a family and sector-angle interval. Returns measured candidates; not a global optimum. Choose search bounds using actual failed constraints.", "parameters": SearchArguments.model_json_schema()}},
    ]
    system = ("You are the physical design exploration agent for Design Continuum. Use only these two deterministic tools. "
              "Hard requirements are immutable. Models propose; tools decide feasibility. Explain a short PUBLIC design rationale, never internal reasoning. All dimensions are computed predictions, never physical measurements; use the word computed. "
              "First diagnose the supplied naive accordion failure; choose which family or parameters to investigate. "
              "A single-row accordion preserves its full b_mm width; packing may rotate in-plane. Miura contracts biaxially but adds creases. "
              "After tool feedback, choose a feasible candidate from a returned ID. Honor the brief's preference among trade-offs. "
              "You must call at least one tool; no invented measurements, material constants, strength, stability or AI advantage claims. "
              "Budget: at most 4 model turns and 6 tool calls, each search at most 512 candidates. "
              'When finished return ONLY JSON: {"selected_id":"a returned 10-character ID","rationale":"brief explanation of measured trade-off and limits"}. '
              "If no feasible result is found, say so without inventing a feasible ID.")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps({
        "brief": brief, "requirements": requirements.model_dump(), "initial_failed_candidate": compact(baseline)})}]
    started, calls, decision = time.monotonic(), 0, None
    error = None
    for turn in range(4):
        payload = {"model": model, "messages": messages, "max_tokens": 4096}
        if turn == 3 or calls >= 6:
            feasible = [c for c in pool.values() if c["feasible"]]
            feasible.sort(key=lambda c: (c["metrics"]["crease_segments"], c["score"]))
            messages.append({"role": "user", "content": "The experiment budget is ending. Finalize now using a previously computed feasible ID. No more tools. " + json.dumps({"computed_feasible_candidates": [compact(c) for c in feasible[:12]]})})
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "candidate_selection", "strict": True, "schema": Decision.model_json_schema()}}
        else:
            payload.update(tools=tools, tool_choice="auto")
        result, response = request(base, key, "/chat/completions", payload)
        trace.append({"kind": "model_request", "turn": turn + 1, "model": model,
                      "http_status": result.get("http_status"), "latency_ms": result.get("latency_ms"),
                      "usage": result.get("usage"), "request_id": result.get("request_id"),
                      "response_model": response.get("model") if response else None})
        if not response:
            error = {"message": "Model request failed", "transport": result}
            break
        try:
            message = response["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            error = {"message": "Invalid model response shape"}
            break
        content = message.get("content") or ""
        if content:
            trace.append({"kind": "public_model_output", "text": content[:5000]})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            try:
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                decision = Decision.model_validate_json(cleaned)
                if calls == 0 or decision.selected_id not in pool or not pool[decision.selected_id]["feasible"]:
                    raise ValueError("Selected ID must be a tool-evaluated feasible candidate")
                break
            except (ValidationError, ValueError) as exc:
                decision = None
                messages += [message, {"role": "user", "content": f"Decision rejected: {str(exc)[:400]}. Use tools or choose a returned feasible ID; do not change requirements."}]
                continue
        messages.append(message)  # Provider reasoning fields are replayed in memory only.
        for tool_call in tool_calls:
            name = tool_call.get("function", {}).get("name")
            arguments = tool_call.get("function", {}).get("arguments", "{}")
            if calls >= 6:
                tool_result = {"error": "Tool-call budget exhausted"}
            else:
                calls += 1
                try:
                    args = json.loads(arguments)
                    if name == "evaluate_design":
                        candidate = evaluate(Design.model_validate(args), requirements)
                        pool[candidate["id"]] = candidate
                        tool_result = compact(candidate)
                    elif name == "search_designs":
                        settings = SearchArguments.model_validate(args)
                        found = search(requirements, **settings.model_dump())
                        for candidate in found["candidates"]:
                            pool[candidate["id"]] = candidate
                        tool_result = {k: found[k] for k in ("evaluated_count", "feasible_count", "pareto_ids", "search_space")}
                        tool_result["candidates"] = [compact(c) for c in found["candidates"][:6]]
                    else:
                        tool_result = {"error": "Unknown tool; only named geometry tools are allowed"}
                except (ValidationError, ValueError, TypeError) as exc:
                    tool_result = {"error": str(exc)[:700]}
            trace.append({"kind": "tool_result", "tool": name, "arguments": arguments[:2000], "result": tool_result})
            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "content": json.dumps(tool_result)})
    if not decision or calls == 0 or decision.selected_id not in pool or not pool[decision.selected_id]["feasible"]:
        decision = None
        error = error or {"message": "No verified final selection within the bounded agent budget"}
    selected = pool[decision.selected_id] if decision else None
    report = {"run_id": uuid.uuid4().hex[:12], "created_at_utc": datetime.now(timezone.utc).isoformat(),
              "provider": provider, "model": model, "brief": brief, "requirements": requirements.model_dump(),
              "baseline": baseline, "selected": selected, "rationale": decision.rationale if decision else None,
              "status": "completed" if selected else "incomplete", "error": error,
              "latency_ms": round((time.monotonic()-started)*1000), "tool_calls": calls, "trace": trace,
              "validation": validate_geometry(Design(**selected["design"])) if selected else None,
              "comparison_limit": "Improvement over one naive starting design; not a benchmark against broad deterministic search."}
    directory = ROOT / "artifacts" / "runs"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (report["run_id"] + ".json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def run_agent(requirements: Requirements, brief: str, provider="baseten", mode="single_pass", objective="creases", seed=101):
    """Default to one planning request; legacy feedback is an explicit API opt-in."""
    if mode == "single_pass":
        from .planner import run_single_pass
        return run_single_pass(requirements, brief, provider, objective, seed)
    if mode == "feedback":
        report = run_feedback_agent(requirements, brief, provider)
        report["mode"] = "feedback"
        return report
    raise ValueError("Unknown planning mode")
