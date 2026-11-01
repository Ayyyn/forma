# 0004 — Continue only a bounded Kresling mechanics research prototype

Date: October 28, 2026. Status: implemented; numerical proof gate passed.

The user replaced the previous project direction with a scientific feasibility investigation of Kresling mechanics, multistability and pre-stress. Do not expand the Miura studio or material-revision workspace as a consequence of their existing code.

Implemented an isolated two-DOF five-term bar-and-hinge energy model from Zang et al., JMPS 2024, plus a declared ideal bilateral axial spring using the PNAS 2025 energy term. Reproduced Appendix A.3 stationary/slice results and 30 independently extracted Figure 5A theoretical samples. Source-curve NRMSE is about 0.208% of full plotted vertical range, within the frozen 2% limit; independent geometry, 70-digit derivative and convergence checks pass.

The planned strong spring leaves one located minimum in the search domain and shifts its equilibrium under preload. A documented weaker-spring sweep retains two minima and tunes the directional branch barriers. All declared outcomes are retained. A shallow angular-well detection issue was found, fixed and regression-tested.

Decision: continue the single-cell numerical research direction; defer UI, branding, fabrication claims, multicell sequences and PINNs. This is not physical validation, independent material calibration, an AI-benefit result or a novelty claim for established origami mechanics. A future inverse-design/experiment-selection task must be compared with a strong deterministic baseline before expansion.

Commands, citations, quantitative evidence, dataset/code availability, unsupported physics and the subsequent benchmark proposal are in [KRESLING_PROOF.md](../docs/KRESLING_PROOF.md). Generated plots, raw calculations and source hashes are under `artifacts/kresling-proof/`.
