"""Offline Forma checks; excludes independent earlier research applications."""

import subprocess
import sys

MODULES = (
    "test_assembly_study",
    "test_design_batching",
    "test_drawing_sections",
    "test_mechanical_print",
    "test_retention_study",
    "test_prismatic_controls",
    "test_lazy_drawing",
    "test_checkpoint_recovery",
    "test_planning_context",
    "test_handling_study",
    "test_export_cache_identity",
    "test_budget",
    "test_component_library",
    "test_crate_agent",
    "test_crate_engine",
    "test_crate_exports",
    "test_workspace_agent",
    "test_workspace_geometry",
    "test_workspace_drawing",
    "test_workspace_workflow",
    "test_workspace_requirements",
    "test_workspace_performance",
    "test_mechanical_features",
    "test_mechanical_validation",
    "test_folding",
    "test_folding_print",
    "test_mesh_import",
    "test_design_agent",
    "test_mechanism_study",
    "test_floor_check",
    "test_motion_probe",
    "test_motion_cache",
    "test_native_study",
    "test_component_exports",
)


if __name__ == "__main__":
    result = subprocess.call(
        [
            sys.executable,
            "-m",
            "unittest",
            *["tests." + name for name in MODULES],
            "-v",
        ]
    )
    if result == 0:
        result = subprocess.call(["node", "--test", "tests/test_motion_video.mjs", "tests/test_lazy_drawing.mjs"])
    raise SystemExit(result)
