"""Run one real, bounded Meta-guided panel exploration and print its public result."""
import argparse
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from continuum.agent import run_agent
from continuum.geometry import Requirements

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--provider", choices=["baseten", "meta"], default="baseten")
args = parser.parse_args()
report = run_agent(Requirements(), "Fit the 120 x 45 x 24 mm pocket, preserve at least 240 x 150 mm deployed extent, and prefer fewer crease segments among feasible designs.", args.provider)
print(json.dumps({k: report[k] for k in ("run_id", "status", "model", "rationale", "selected", "validation", "tool_calls", "latency_ms", "error")}, indent=2))
raise SystemExit(0 if report["status"] == "completed" else 1)
