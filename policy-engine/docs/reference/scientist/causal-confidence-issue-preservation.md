# Confidence issues survive degraded simulation loading

`ConfidencePass` retains every issue established before loading a simulation
artifact. When a shaped `simulation_result_ref` points to missing CAS bytes,
malformed JSON, or a payload rejected by `SimulationResult`, the pass appends
`CONFIDENCE_SIM_RESULT_LOAD_FAILED` as a warning and returns its accumulated
issues. A sibling artifact failure cannot replace an existing blocker.

This matters when an offered `causal_envelope_ref` has already caused
`CONFIDENCE_GATE_ELIGIBILITY_LOW`: the causal-purpose input remains a non-gating
candidate even if its envelope says `gate_eligible=True`, is labelled
`ensemble`, offers an identification proof, or the minimum gate ratio is zero.
The consumer role survives simulation load failures, missing stores, unresolved
envelopes, and successful simulation reads. Healthy simulation metrics cannot
dilute that role.

The existing noncausal confidence profile keeps its behavior: a failed
simulation load emits its warning, an empty simulation has no envelope issues,
and a healthy simulation is evaluated against the configured thresholds.
Issue codes, severity values, reference locations, and public report schemas
are unchanged.

This repair closes the issue-list replacement escape identified as the same
consumer-role-drop class in G's `F-delta-owner-actions-2026-10-06.md` action 2.
It does not supply an identification issuer or verifier. Positive causal
identification admission, admitted production inputs, and a production TMLE
workload/budget witness remain limited or UNRUN until the existing responsible
owners supply their current source/graph/estimand/target and execution-context
bindings. A numerical SUCCESS status or interval cannot establish those inputs.

Verification runs the canonical pass against persisted envelopes and real
`FileSystemCAS` simulation artifacts through fresh readers. The regression
matrix tests both reference locations and zero/full gate-ratio thresholds;
the property-removal control restores the singleton warning return while
preserving the pass, issue codes, types, source labels, and artifact references.
