# 0006 — Reopen actuator design with a more capable tool architecture

Date: October 29, 2026. Status: proposed next experiment; no new AI benefit established.

The user requested a more ambitious reassessment of origami actuators, tool availability, geometric context and system design for Push the Frontier. The earlier frozen experiment-selection failure remains unchanged. Its interface only allowed an experiment ID and did not measure numerical-tool-using design or repair. A broad conclusion against all origami actuator work was not justified.

Research supports a bounded new task: composing and sizing guided coaxial Kresling actuator modules for requested stroke, end twist, envelope, force and constrained local stability. Published tendon/pneumatic/modular actuator work is prior art; a general multi-DoF robot requires physics the current cell model does not support.

A new unscored offline probe demonstrates a substantive failure/repair: opposite-handed geometry cancels end twist, but the symmetric bare pair at 20 mm total compression is unstable to internal redistribution. An ideal 0.25 N/mm axial spring per cell makes this modeled state a strict constrained local minimum while increasing reaction force. Independent summed vertex energies confirm the Hessian sign and derivatives. No Meta model generated this repair and no physical test was made. It is a development case excluded from later holdouts.

Next architecture: typed authoritative design state, numerical optimizer, constrained-equilibrium/stability tools, exact geometry context, optional rendered views, sensitivity analysis and independent verification. Compare against the same optimizer behind an enumerating deterministic controller and a one-pass Meta brief compiler. Charge internal physics work fairly and evaluate new held-out tasks after an explicitly separate freeze. More tools or a different problem do not themselves prove AI value.

Historical API receipts were re-audited: all 192 earlier requests returned HTTP 200 with unique provider IDs and usage; 184 usable choices and eight length-limited responses. This turn made no new Meta requests and no paid AI benchmark run.

See `docs/ACTUATOR_SECOND_ATTEMPT.md` for sources, proposed architecture, scientific limits, attribution and evaluation design. The existing no-go applies to the prior selector configuration; this proposal is a new capability question, not a replacement result.
