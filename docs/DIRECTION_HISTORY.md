# Mechanical project directions

## Current: structured engineering investigation workbench (October 30)

Code and own work log: `mechanical_workbench/`.
Run: `python -m mechanical_workbench serve --port 8770`.
Viewer: http://127.0.0.1:8770/
Read `mechanical_workbench/README.md` and `mechanical_workbench/WORK_LOG.md`.

The first slice is multi-load spatial-frame diagnosis, virtual calibration,
immutable design revisions, shared numerical sizing and independent verification.
It is a foundation for behavior-driven structure design, not a claim that arbitrary
nonlinear structures, contacts or functional fabricated mechanisms are solved.

## Preserved: earlier structure/origami discovery research

All earlier original code, experiment results and the old viewer remain in place.
The old viewer remains at http://127.0.0.1:8767/.

Verified checkpoint: `checkpoints/2026-10-30-before-mechanical-workbench-v2/`.
It contains 1,525 files, a ZIP with per-file SHA-256 hashes, and `RESTORE.md`.
The first checkpoint is also retained; v2 corrects its exclusion of the bundled
frontend plot library. Credentials and installed research runtimes are excluded.
Pinned requirements and saved outputs are included.

Verify without touching originals:

```powershell
python research/checkpoint_direction.py verify
```

Extract an independent copy; existing targets and workspace-root replacement are
refused:

```powershell
python research/checkpoint_direction.py extract --destination restored/previous-direction
```

The archive does not need to be restored to continue the earlier direction:
its original directories are still here. Nothing in the new workbench requires
overwriting `nonlinear_discovery`, `robust_discovery`, `discovery_board`, their
results, or the earlier CAD exports. Root documentation for unrelated work is
also preserved. The new direction keeps its own work log rather than replacing
the earlier log.
