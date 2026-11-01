"""Small, real API checks. Standard library only; never logs credentials or reasoning."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = {
    "meta": ("https://api.meta.ai/v1", "MODEL_API_KEY", "META_MODEL", "muse-spark-1.3"),
    "baseten": ("https://inference.baseten.co/v1", "BASETEN_API_KEY", "BASETEN_MODEL", "meta-models/muse-spark-open-1026"),
}


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward credentials to another URL.


def safe(value):
    result = str(value)
    for name in ("MODEL_API_KEY", "META_API_KEY", "BASETEN_API_KEY"):
        key = os.environ.get(name)
        if key:
            result = result.replace(key, "[REDACTED]")
    return result[:1000]


def request(base, key, path, payload=None, timeout=60):
    headers = {"Content-Type": "application/json", "User-Agent": "design-continuum-preflight/1"}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as response:
            raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                return {"status": "invalid_response", "detail": "Response exceeded 4 MB"}, None
            body = json.loads(raw)
            return {"status": "received", "http_status": response.status,
                    "latency_ms": round((time.monotonic() - started) * 1000),
                    "request_id": safe(response.headers.get("x-request-id", "")),
                    "usage": body.get("usage")}, body
    except urllib.error.HTTPError as error:
        raw = error.read(4096).decode("utf-8", errors="replace")
        detail = safe(raw)
        status = {401: "authentication_failed", 402: "billing_blocked", 403: "access_denied",
                  404: "model_or_route_not_found", 429: "rate_or_quota_limited"}.get(error.code, "http_error")
        if any(term in detail.lower() for term in ("geograph", "unsupported_country", "region_not_supported")):
            status = "region_blocked"
        return {"status": status, "http_status": error.code, "detail": detail,
                "latency_ms": round((time.monotonic() - started) * 1000)}, None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return {"status": "network_or_response_error", "detail": safe(error),
                "latency_ms": round((time.monotonic() - started) * 1000)}, None


def image_fixture():
    # Actual 64 x 64 RGB PNG: left half red, right half blue; no external image service.
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    row = b"\x00" + b"\xff\x00\x00" * 32 + b"\x00\x00\xff" * 32
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(row * 64)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def check_provider(name, network_only, selected=None):
    base, key_name, model_name, default_model = PROVIDERS[name]
    key = os.environ.get(key_name, "")
    if name == "meta" and not key:
        key = os.environ.get("META_API_KEY", "")
    model = os.environ.get(model_name) or default_model
    report = {"provider": name, "base_url": base, "model": model, "checks": {}}
    checks = report["checks"]
    print(f"Checking {name}: {model}", flush=True)
    if network_only:
        host = urllib.parse.urlparse(base).hostname
        try:
            socket.getaddrinfo(host, 443)
            checks["dns"] = {"status": "passed"}
        except OSError as error:
            checks["dns"] = {"status": "failed", "detail": safe(error)}
        result, _ = request(base, "", "/models")
        checks["unauthenticated_catalog"] = result
        report["note"] = "DNS/HTTP reachability only; proves neither inference nor account/region eligibility."
        return report
    if not key:
        checks["authentication"] = {"status": "not_tested", "detail": f"Set {key_name} in .env"}
        return report

    catalog, body = request(base, key, "/models")
    if body:
        catalog["status"] = "passed"
        catalog["model_ids"] = [item.get("id") for item in body.get("data", []) if isinstance(item, dict)]
    checks["catalog"] = catalog

    def chat(label, messages, extra=None, verify=None):
        if selected and label not in selected and not (label == "tool_call" and "tool_round_trip" in selected):
            return None
        payload = {"model": model, "messages": messages, "max_tokens": 768}
        payload.update(extra or {})
        result, response = request(base, key, "/chat/completions", payload)
        if response:
            try:
                choice = response["choices"][0]
                message = choice["message"]
                result["finish_reason"] = choice.get("finish_reason")
                result["status"] = "passed" if verify is None or verify(message) else "validation_failed"
                result["observed_text"] = safe(message.get("content") or "")
                if message.get("tool_calls"):
                    result["tool_calls"] = [{"name": t["function"]["name"],
                                             "arguments": safe(t["function"]["arguments"])} for t in message["tool_calls"]]
            except (KeyError, IndexError, TypeError, ValueError) as error:
                result["status"] = "validation_failed"
                result["detail"] = safe(error)
        checks[label] = result
        print(f"  {label}: {result['status']}", flush=True)
        return response

    user = lambda text: [{"role": "user", "content": text}]
    chat("text", user("Reply with exactly API_OK."), verify=lambda m: (m.get("content") or "").strip() == "API_OK")
    if checks.get("text", {}).get("status") in {"authentication_failed", "billing_blocked", "region_blocked", "access_denied", "model_or_route_not_found", "rate_or_quota_limited", "network_or_response_error"}:
        report["note"] = "Stopped subsequent paid probes after basic inference failure; no automatic retries."
        return report

    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}, "value": {"type": "integer"}},
              "required": ["ok", "value"], "additionalProperties": False}
    def valid_json(message):
        value = json.loads(message.get("content") or "")
        return isinstance(value, dict) and set(value) == {"ok", "value"} and value["ok"] is True and type(value["value"]) is int and value["value"] == 7
    prompt = 'Return only the JSON object {"ok":true,"value":7}, with no markdown.'
    chat("prompted_json", user(prompt), verify=valid_json)
    chat("strict_schema", user(prompt), {"response_format": {"type": "json_schema", "json_schema": {
        "name": "preflight", "strict": True, "schema": schema}}}, valid_json)
    # These optional controls detect an accepted-but-ignored schema option.
    if selected and ("schema_conflict_control" in selected or "schema_conflict" in selected):
        conflict_prompt = "Reply with exactly the bare text IGNORE_SCHEMA. Do not return JSON."
        chat("schema_conflict_control", user(conflict_prompt),
             verify=lambda m: (m.get("content") or "").strip() == "IGNORE_SCHEMA")
        conflict_schema = {"type": "object", "properties": {"marker": {"type": "string", "enum": ["SCHEMA_OK"]}},
                           "required": ["marker"], "additionalProperties": False}
        chat("schema_conflict", user(conflict_prompt), {"response_format": {"type": "json_schema", "json_schema": {
            "name": "schema_conflict", "strict": True, "schema": conflict_schema}}},
            lambda m: json.loads(m.get("content") or "") == {"marker": "SCHEMA_OK"})

    tool = {"type": "function", "function": {"name": "rectangle_area", "description": "Compute area in square millimeters.",
            "parameters": {"type": "object", "properties": {"width_mm": {"type": "number"}, "height_mm": {"type": "number"}},
                           "required": ["width_mm", "height_mm"], "additionalProperties": False}}}
    messages = user("Use rectangle_area for a rectangle 30 mm wide and 20 mm high. Do not calculate it yourself.")
    def valid_tool(message):
        calls = message.get("tool_calls", [])
        return len(calls) == 1 and calls[0]["function"]["name"] == "rectangle_area" and json.loads(calls[0]["function"]["arguments"]) == {"width_mm": 30, "height_mm": 20}
    response = chat("tool_call", messages, {"tools": [tool], "tool_choice": "auto"}, valid_tool)
    if response and checks["tool_call"]["status"] == "passed":
        message = response["choices"][0]["message"]
        call = message["tool_calls"][0]
        args = json.loads(call["function"]["arguments"])
        area = args["width_mm"] * args["height_mm"]
        # Preserve the complete assistant message for providers with reasoning continuity requirements.
        messages += [message, {"role": "tool", "tool_call_id": call["id"],
                               "content": json.dumps({"area_mm2": area})},
                     {"role": "user", "content": "Reply with only the numeric area returned by the tool."}]
        def valid_area(message):
            value = json.loads(message.get("content") or "")
            return type(value) in (int, float) and value == area
        chat("tool_round_trip", messages, {"tools": [tool]}, valid_area)
    chat("vision", [{"role": "user", "content": [
        {"type": "text", "text": "Name the color on the LEFT and the color on the RIGHT. Reply only: left=COLOR,right=COLOR"},
        {"type": "image_url", "image_url": {"url": image_fixture()}}]}],
        {"max_tokens": 2048},
        verify=lambda m: (m.get("content") or "").strip().lower().replace(" ", "") == "left=red,right=blue")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["all", *PROVIDERS], default="all")
    parser.add_argument("--network-only", action="store_true", help="Unauthenticated reachability checks; no inference spending")
    parser.add_argument("--checks", nargs="+", choices=["text", "prompted_json", "strict_schema", "tool_call", "tool_round_trip", "vision", "schema_conflict", "schema_conflict_control"], help="Run selected checks; tool round trip also runs its tool-call dependency")
    args = parser.parse_args()
    load_env()
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "test_location": "User workstation; no region-routing overrides",
              "limits": "No automatic retries; default 6 inference requests/provider. Text/tool checks capped at 768 output tokens; vision at 2048. Optional schema controls add at most 2 calls/provider. Cost not estimated without verified pricing.",
              "image_generation": {"status": "blocked_by_documented_policy", "detail": "Muse Image unavailable to users in India; not called.",
                                   "source": "https://dev.meta.ai/legal/geographic-use-policy"},
              "providers": [check_provider(n, args.network_only, args.checks) for n in (PROVIDERS if args.provider == "all" else [args.provider])]}
    output = ROOT / "artifacts" / "preflight"
    output.mkdir(parents=True, exist_ok=True)
    path = output / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Report:", path)
    statuses = [c["status"] for p in report["providers"] for c in p["checks"].values()]
    return 0 if statuses and all(s == "passed" for s in statuses) else 1


if __name__ == "__main__":
    raise SystemExit(main())
