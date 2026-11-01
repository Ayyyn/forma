"""Bounded checks of other catalogued Meta models, with synthetic fixtures only."""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import struct
import time
import urllib.error
import urllib.request
import uuid
import wave
import zlib

from api_preflight import ROOT, NoRedirect, load_env, request, safe

BASE = "https://api.meta.ai/v1"


def text_probe(model, key, base=BASE):
    result, body = request(base, key, "/chat/completions", {
        "model": model, "messages": [{"role": "user", "content": "Reply with exactly API_OK."}],
        "max_tokens": 2048,
    })
    if body:
        try:
            choice = body["choices"][0]
            text = choice["message"].get("content") or ""
            result.update(status="passed" if text.strip() == "API_OK" else "validation_failed",
                          response_model=body.get("model"), observed_text=safe(text), finish_reason=choice.get("finish_reason"))
        except (KeyError, IndexError, TypeError) as error:
            result.update(status="validation_failed", detail=safe(error))
    print(f"{model}: {result['status']}", flush=True)
    return {"model": model, "base_url": base, "check": "text", **result}


def rectangle_image():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    pixels = b"".join(b"\x00" + b"".join(
        b"\xff\x00\x00" if 64 <= x < 192 and 80 <= y < 176 else b"\xff\xff\xff"
        for x in range(256)) for y in range(256))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def sam_probe(key):
    result, body = request(BASE, key, "/responses", {
        "model": "sam-3.1", "stream": False,
        "input": [{"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "red rectangle"},
            {"type": "input_image", "image_url": rectangle_image()}]}],
        "metadata": {"mask_encoding": "one_bit"},
    })
    if body:
        texts = [c.get("text", "") for item in body.get("output", []) for c in item.get("content", [])
                 if c.get("type") == "output_text"]
        output = "".join(texts) or body.get("output_text", "")
        boxes = []
        for match in re.finditer(r"<\|box;([^|]+)\|>", output):
            fields = dict(part.split("=", 1) for part in match.group(1).split(";") if "=" in part)
            try:
                b = {n: int(fields[n]) for n in ("x1", "y1", "x2", "y2", "w", "h")}
                intersection = max(0, min(b["x2"], 192) - max(b["x1"], 64)) * max(0, min(b["y2"], 176) - max(b["y1"], 80))
                union = (b["x2"] - b["x1"]) * (b["y2"] - b["y1"]) + 128 * 96 - intersection
                b["iou_with_fixture"] = intersection / union if union > 0 else 0
                b["bounds_valid"] = b["w"] == b["h"] == 256 and 0 <= b["x1"] < b["x2"] <= 256 and 0 <= b["y1"] < b["y2"] <= 256
                boxes.append(b)
            except (KeyError, ValueError):
                pass
        has_mask = "<|mask;" in output
        passed = body.get("status") == "completed" and has_mask and any(b["bounds_valid"] and b["iou_with_fixture"] >= 0.5 for b in boxes)
        result.update(status="passed" if passed else "inference_received_validation_inconclusive",
                      response_status=body.get("status"), response_model=body.get("model"), boxes=boxes,
                      mask_payload_present=has_mask, output_preview=safe(output),
                      limitation="Mask payload presence checked; mask pixels not decoded. One synthetic image, no video tracking test.")
    print(f"sam-3.1: {result['status']}", flush=True)
    return {"model": "sam-3.1", "check": "image_segmentation", **result}


def voice_probe(key, path):
    if not path.exists():
        return {"model": "muse-voice-transcribe-1.0", "status": "not_tested", "detail": "Missing synthetic speech WAV"}
    with wave.open(str(path), "rb") as audio:
        assert audio.getnchannels() == 1 and audio.getsampwidth() == 2 and audio.getframerate() in (16000, 24000)
        duration = audio.getnframes() / audio.getframerate()
    boundary = "preflight" + uuid.uuid4().hex
    config = json.dumps({"model": "muse-voice-transcribe-1.0", "mode": "PUSH_TO_TALK", "audioEncoding": "WAV"})
    data = (f'--{boundary}\r\nContent-Disposition: form-data; name="request"\r\nContent-Type: application/json\r\n\r\n{config}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="synthetic.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()
    data += path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + "/asr/transcribe", data=data, headers={
        "Authorization": "Bearer " + key, "Content-Type": "multipart/form-data; boundary=" + boundary,
        "Accept": "application/json", "User-Agent": "design-continuum-preflight/1"})
    started = time.monotonic()
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
            body = json.loads(response.read(1_000_000))
            text = body.get("transcript", "")
            words = set(re.findall(r"[a-z]+", text.lower()))
            passed = {"red", "rectangle", "wide", "high"}.issubset(words)
            result = {"status": "passed" if passed else "inference_received_validation_inconclusive",
                      "http_status": response.status, "transcript": safe(text), "audio_duration_seconds": round(duration, 3),
                      "response_audio_duration_ms": body.get("audioDurationMs"), "request_id": safe(response.headers.get("x-request-id", ""))}
    except urllib.error.HTTPError as error:
        result = {"status": "http_error", "http_status": error.code, "detail": safe(error.read(4096).decode(errors="replace"))}
    except (OSError, ValueError) as error:
        result = {"status": "network_or_response_error", "detail": safe(error)}
    result["latency_ms"] = round((time.monotonic() - started) * 1000)
    print(f"muse-voice-transcribe-1.0: {result['status']}", flush=True)
    return {"model": "muse-voice-transcribe-1.0", "check": "file_transcription", **result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speech-wav", type=Path, default=ROOT / "artifacts/preflight/synthetic-speech.wav")
    args = parser.parse_args()
    load_env()
    key = os.environ.get("MODEL_API_KEY") or os.environ.get("META_API_KEY")
    if not key:
        raise SystemExit("Set MODEL_API_KEY locally before testing")
    models = ["muse-wonder-1.0", "muse-spark-1.2", "muse-spark-1.1", "muse-spark-1.3-contributor", "muse-spark-1.2-contributor"]
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda m: text_probe(m, key), models))
    results.append(sam_probe(key))
    results.append(voice_probe(key, args.speech_wav))
    if os.environ.get("BASETEN_API_KEY"):
        results.append(text_probe("meta-models/muse-spark-open", os.environ["BASETEN_API_KEY"], "https://inference.baseten.co/v1"))
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "One text call per additional text model; one SAM image and one prerecorded synthetic-speech transcription. No retries or GPU deployment.",
              "data": "Synthetic markers, generated rectangle PNG, and Windows synthetic speech only. Contributor variants received no user content.",
              "results": results}
    out = ROOT / "artifacts/preflight" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-other-models.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Report:", out)
    return 0 if all(r["status"] == "passed" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
