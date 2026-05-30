# Policy Design Case Wave 2 Closeout

Owner: `team-policyos-runtime`
Date: 2026-05-22
Status: `closed`

## Scope

Wave 2 closes the shared carriers, registries, and telemetry primitives that
Wave 3 producer adapters can target without direct peer dependencies:

- W2.A concept spine and handshake kernel: `implemented`
- W2.B rule evolution registry: `implemented`
- W2.C cost and degradation primitives: `implemented`
- W2.D self-FMEA and soft-gate telemetry: `implemented`
- W2.E calibration ledger schema: `implemented`
- W2.F balanced memory schema: `implemented`
- I2 walking skeleton: `implemented`

Relevant refs: `E6`, `E14`, `E18`, `E19`, `E20`, `E21`, `C21`, `C23`,
`C24`, `C25`, `C28`, `C33`, `C35`, `C37`, `C40`, `C41`, `P02`, `P04`,
`P06`, `P07`, `P08`, `P09`, `P10`, `P11`, `P12`, `P13`, and `P15`.

## Evidence

| Evidence | Path |
| --- | --- |
| Concept spine and producer handshake kernel | `src/polisyos/runtime/quality/concept_spine.py` |
| Evidence-spine handoff ledger | `src/polisyos/runtime/quality/evidence_spine_handoff.py` |
| Rule evolution registry | `src/polisyos/runtime/quality/rule_evolution.py` |
| Cost/degradation telemetry | `src/polisyos/runtime/quality/cost_degradation.py` |
| Soft-gate telemetry | `src/polisyos/runtime/quality/soft_gate_telemetry.py` |
| Calibration ledger | `src/polisyos/runtime/quality/calibration_ledger.py` |
| Balanced memory influence records | `src/polisyos/runtime/quality/memory_influence.py` and `src/polisyos/scientist/orchestration/memory/balanced.py` |
| I2 runtime walking skeleton | `src/polisyos/runtime/quality/wave2_walking_skeleton.py` |
| Persisted I2 walking skeleton bundle | `architecture/policy_design_case/wave2_i2_walking_skeleton/manifest.json` |
| Capability reality report | `architecture/policy_design_case/capability_reality_report.json` |
| I2 semantic/e2e tests | `tests/unit/runtime/quality/test_wave2_walking_skeleton.py` |

The I2 builder emits one trivial request, one reconciled concept spine record,
one deterministic producer fixture, one producer handshake ledger, one
evidence-spine handoff ledger, one claim registry entry, one closeout verdict,
one typed projection, and one semantic negative proving historical priors
cannot enter current-run claim evidence slots.

## Pattern Pass

- Relevant IDs: `P01`, `P02`, `P04`, `P07`, `P08`, `P09`, `P10`, `P11`,
  `P12`, `P13`, and `P15`.
- Existing anti-patterns closed: W2.A no longer remains only
  `implemented_but_not_orchestrated`; the I2 seam connects concept spine,
  producer handshake, handoff ledger, claim registry, closeout reader, and
  projection.
- Correct pattern: runtime-owned carriers are consumed by downstream readers
  and retain authority boundaries. Cost and review telemetry stay advisory
  until governed policy/ADR maturity permits blocking.
- Missing capability labels: none for Wave 2 exit. W2.F external surfaces remain
  explicitly governed as `surface_out_of_scope` evidence under ADR-0172 until
  Wave 5 surfaces.
- Acceptance signal: the I2 walking skeleton passes end-to-end, and semantic
  negatives reject projection closeout substitution and historical-prior
  evidence-slot laundering. The capability reality report contains W2.A-F and
  W2.I2 as implemented claims with traceability rows.

## Validation

Run from `policy-engine/` on 2026-05-22:

```bash
uv run python tools/quality/validation/check_policy_design_case_capability_ratchet.py --repo-root .
uv run pytest tests/unit/runtime/quality/test_wave2_walking_skeleton.py tests/unit/runtime/quality/test_closeout_reader.py::test_cost_degradation_telemetry_is_observable_not_required_closeout_blocker -q
uv run pytest tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py -q
uv run pytest tests/unit/runtime/quality -q
uv run pytest tests/unit/scientist/orchestration -q
```

The Wave 2 validation commands passed locally. The orchestration suite retains
the existing skipped SLO alerting-rules case when that fixture file is absent.

## Residual

Wave 2 intentionally does not implement broad Lex, Fabric, Scholar, Foundry,
Data Forge, or Scientist adapters. Those remain Wave 3 work, now targeting the
stable Wave 2 carriers and the I2 runtime seam.
