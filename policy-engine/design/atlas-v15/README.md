# Atlas v15 Source Archive

Owner: team-design

This directory stores the user-provided Atlas v15 design-system archive as a
stable repo evidence source for DS0 admission work and the completed DS2
item-level adjudication.

Archive:

- `PolicyOS_Atlas_Design_System-15_Best_in_Class_Readiness.zip`

SHA-256:

```text
28d3e51dd452a074d30b7a0afa439302c48d4c208307a6a2d09beb935f71a969
```

Admission posture:

- This archive is a design source, not a production frontend package.
- Relative to `policy-engine`, it remains `implemented_but_not_orchestrated`.
  DS0 recorded it as `evidence_source_pending_adjudication`; DS2 has now
  adjudicated every normalized item and changes its post-adjudication source
  disposition to `retained_as_material`. DS4 owns any later production
  migration of an admitted item.
- The governing disposition is
  [`docs/brand/ATLAS_SOURCE_OF_TRUTH.md`](../../docs/brand/ATLAS_SOURCE_OF_TRUTH.md#atlas-d1).
- The historical source-level MACHINE record is
  [`architecture/atlas_surfaces/adoption-ledger.example.json`](../../architecture/atlas_surfaces/adoption-ledger.example.json);
  its pre-DS2 `defer` verdict is not an item-level decision. The completed
  item-level MACHINE record is
  [`architecture/atlas_surfaces/atlas-v15-adoption-ledger.json`](../../architecture/atlas_surfaces/atlas-v15-adoption-ledger.json),
  and its 1,476-member coverage proof is
  [`architecture/atlas_surfaces/atlas-v15-archive-map.json`](../../architecture/atlas_surfaces/atlas-v15-archive-map.json).
- The human adjudication is
  [`docs/reference/frontend/atlas-v15-adjudication.md`](../../docs/reference/frontend/atlas-v15-adjudication.md).
  Wholesale package import, compiled mirrors as authority, synthetic Figma
  parity, the phantom timeline, and point-centric uncertainty as DS16 truth
  are rejected. Selected items remain eligible only under their individual
  `admit_after_refactor` or `wrap_then_strangle` gates.
- Archive `PASS`, `stable`, release, or Figma labels do not prove repo
  consumers, browser behavior, manual assistive-technology evidence, authority
  compatibility, or package publishability.
- If any archive evidence is promoted as long-lived reviewed evidence, promote
  that reviewed evidence through `docs/archive/reports/` or a registered
  generated-artifact family.
