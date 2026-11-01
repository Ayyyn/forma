# Optical forward proof and Meta-written search programs

Run from `C:\Users\LENOVO\meta_hack`:

```powershell
python -m coating_proof
python -m unittest discover -s tests -p test_coating_proof.py -v
python -m unittest discover -s tests -p test_coating_program.py -v
python research/frontier_scout/audit_coating_programs.py
```

These are offline checks; no API calls. Requirements are pinned in `requirements-frontier.txt`. Measured material data and the pure-Python external reference wheel are retained under `research/frontier_scout/vendor/` with receipts/licenses; no globally installed reference package required. `python -m coating_proof` produces the conventional-grid forward report, not an AI discovery.

Inspect `benchmarks/coating-program-probe-v1/summary.json`, `comparison.png`, `independent-audit.json`, `program-*.py` and public API receipts. Program files are received model outputs used as **data** by `NumericProgram`; do not execute them directly with Python. The first two were rejected by the numerical interpreter; the third runs unchanged. Original failed traces remain. Program0's `int(j/2)` encountered the language's exact-integer conversion rule, which is stricter than ordinary Python truncation. Program1 exceeded the1200-node bound. These are interface failures, not evidence of impossible algorithms. A future language revision needs a new frozen protocol; do not silently repair these scored outputs.

Live `meta` runs require local `.env` credentials and consume credits. Existing probe paths cannot be frozen again; original requests cannot automatically be redispatched if a response is pending. All three planned calls are already complete. Report/replay commands do not call the provider:

```powershell
python research/frontier_scout/coating_program_probe.py report
python research/frontier_scout/audit_coating_programs.py
```

Numerical results: ideal coherent isotropic planar films, n/k from particular published material samples, semi-infinite substrate. No process/fabrication/cooling or continuous-tolerance validation. Fixed layer ordering in the probe. Read `docs/COATING_PROGRAM_PROBE.md`, `docs/FRONTIER_SCOUT_RESULTS.md` and `docs/FRONTIER_OPPORTUNITIES_2026_10_30.md` for methods, limits, prior art and recommendations. No general AI superiority or new material claim.
