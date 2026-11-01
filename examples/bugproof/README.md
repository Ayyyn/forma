# Execution-backed examples

`bytes-method-suite.json` contains actual Meta-authored test contracts for the historical Requests byte-method bug. Its source response ID and unmodified proposal are retained. The model checks byte-valued GET, POST and DELETE, plus an ordinary string control.

From the project root, with the prepared pinned fixtures:

```powershell
python -m bugproof_pilot_v2 check --case psf__requests-2317 --variant buggy --suite examples/bugproof/bytes-method-suite.json
python -m bugproof_pilot_v2 check --case psf__requests-2317 --variant fixed --suite examples/bugproof/bytes-method-suite.json
```

Expected process exit codes are **1** for the buggy variant and **0** for the fixed variant. Requests are prepared locally with actual upstream code; transport is recorded, not sent to a server.

`fresh-parser-suite.json` contains actual Meta-authored message/assertion data for a newly reproduced local adapter defect. Run the complete original/corrected/overbroad-mutant check with no model calls:

```powershell
python scripts/probe_fresh_parser_bug.py --replay
```

The correction was written separately by the project author. Meta generated the test inputs and expected outcomes. This example does not certify complete fix correctness.

See `docs/PIVOT_BUG_REPROOF.md` for research, provenance, costs, limits and the failed overall pilot gate. General repository execution and a product UI are not implemented.
