# F Fry / CAU delta review

Independent read-only review of the immutable F snapshots in `R/1740-new-head-triage.json` and `after-checkpoint11-ref-delta.json` (delta SHA-256 `e1bcd91f5c213d71e4d3165d0ea48b4efdf10cde4b73e7eeb8bba308f0388c3a`). No tests were run for this review.

## Pins and scope

| Lane | Previous → topic head | Slice candidate / tree | Receipt |
|---|---|---|---|
| Fry family/layout continuation | `ad8f0f7532022014c028d74d872c93fe3349d220` → `e00dd3799cf2cdd14baf4b26e175ba1e848c3a6a` (head tree `e3b5d33af335747d5b5aa932adc54e3b8dc62870`) | `3e1819173f0593ce93d257c3c62cdb2fa627e426` / `45852a68bb786a96d6d23c52cea790f13d3489d3` | `implementation-handoffs/F/family-layout-consumers-20261006.json` |
| CAU consumer continuation carried by F closeout | `421f1dd977b237307394c68820caab4156716eb2` → `39133d4d8b9a680942ffeb983385cbee1b1b493a` (head tree `cf0ffd810e73da253bf9151b41d71fdc4e80ee77`) | `3afb3ea5f26ad429ac45be78bd2cbd180fcc5a77` / `508884be8ea79e5b87844030ea4122c8e74d610a` | `implementation-handoffs/F/causal-consumer-boundaries-continuation-20261006.json` |

The triage pins show both candidates present, tree-matching their receipts, based on an ancestor, and ancestral to their topic heads. The CAU slice’s changed footprint is six paths: the actual `run_causal_evaluation.py` consumer, its two focused test modules, a reference doc, and two release fragments. The broader `39133…` head carries many other F slices; this review reuses their receipts and does not claim a full closeout review.

## Fry finding

The new Fry receipt is for `family-layout-consumers-20261006` (closure IDs LA-002 and LA-037), not for the output-monitor alias-count property. The `output_monitor.py` change in this delta adds only the `Args`/`Returns` docstring; the function body and normalization path are unchanged from the previously reviewed monitor candidate (`ec6944c…` and the topic base have the same source blob). The candidate still checks canonical `slot_outputs` and raw output independently, then deduplicates with `list(dict.fromkeys([*slot_flags, *raw_flags]))`.

That equality check does not use the alias-normalization correspondence. The real dispatcher maps raw `report` to canonical `result`; for a shared NaN/Inf value the two flags have different keys and survive deduplication. The changed tests exercise family/catalog/layout migration, not anomalous aliases. The existing dispatcher alias case uses finite/empty values, so it does not distinguish the duplicate-count failure. No current Fry delta repairs the previously reported `NEW_CLASS` dual-view double-count. Keep the exactly-once warning/metric claim **HOLD** until a real dispatcher control proves one canonical anomaly for the aliased value while a distinct raw sidecar still emits its own anomaly. The family/layout receipt’s bounded migration outcome is independent of that hold.

## CAU finding

The new CAU consumer does advance the previously missing runtime binding. Before verifier admission or job execution, `_actual_causal_input_identities` reads the actual selected `ArtifactRef` through Core CAS, checks the actual bytes and manifest (ID, kind, media type, size, integrity, and store verification), and compares the resulting byte digest identity against both the EvalSafety context and input-provenance set. Optional staged refs must be complete and identities may not be duplicated. The canonical consumer preserves the selected typed ref across reads and lineage; an exact-candidate scan found no remaining bare-artifact-ID `get_bytes`/`get_manifest`/`verify` call in this owner.

At the real Standard/Staggered DiD job boundary, the consumer reconciles the persisted report/envelope with the job projection, reloads the current panel, and recomputes the complete diagnostic input/result contract separately from the fixed scalar target. A changed `time_treatment` with the same target is refused; coherent diagnostic/hash substitution and marker-only controls are refused. The fresh reader keeps `identification_authority=False`; non-rejection remains descriptive evidence only.

The exact-candidate receipts are substantive: `root-input-views/stdout` is 47 passed with three empty-array monitor warnings; the frozen independent selector is 23 passed on `3afb3ea…`. The independent same-bytes/two-manifest fixture proves that the actual resolver/consumer/lineage use the selected view, and a property-removal control restoring the three reads to bare IDs makes the actual consumer refuse the valid selected view. The independent DiD oracle reports the hand-computed slope/HC1/Normal result `[-0.15, 0.0704166667, 0.5718922636]`; the prior producer/Statsmodels evidence remains pinned separately at `0b522…`. The independent review records earlier harness-source failures and one environment-import error as nondeciding; the corrected frozen collection and current-candidate native runs are the deciding outputs.

Verdict: **GO, bounded** for Core CAS byte identity, typed-view continuity, and the finite actual DiD job/CAS reader path. This closes the earlier gap for an actual Scientist consumer of the selected panel bytes, rather than just a portable report helper. It does **not** establish a distinct PDC semantic-hash contract or an admitted positive authority decision: both are explicitly `UNRUN` in the current receipt. The whole current EvalSafety appointment/challenge, production inputs, and real parallel-trends identification also remain outside this PASS. The `did.py` producer blob is unchanged across `0b522…`, `86e7f9a…`, `3afb3ea…`, and `39133d4…`; previous producer/math evidence carries, while the 3afb receipt supplies the new consumer proof. No full producer replay is warranted by this delta.

## LA-016 status reconciliation

The authoritative LA-016 source card is the DiD umbrella-wrapper migration criterion: equivalent effective requests from both wrappers produce the same result and warnings; the default registry does not offer the deprecated generic route for new planning; old replay inputs remain consistent. This is separate from PDC semantic identity and does not require inventing a new public authority service.

The CAU continuation receipt lists LA-016 only as related, has `closure_ids: []`, and makes no finding-closure claim. The conflict remains in the carried records: `did-diagnostic-basis-20261006.json` reports `/per_finding/LA-016` as `closed`, while its `original-criteria-reconciled.json` says `limited`; the later `did-selected-cohort-20261006.json` also leaves LA-016 `limited`, citing the retained direct-import replay adapter and unadmitted external frozen-plan/supported-import census. `cau-cohort-admission.json` separately tells G to reconcile its DoWhy residual text against the DiD source card. Preserve **limited / G adjudication pending** until those records are reconciled against the exact card and the three acceptance elements; neither this consumer delta nor its related-ID list closes LA-016.

## Deciding references

- `R/1548-F-causal-fry.md` — unchanged prior alias counterexample and original CAU producer review.
- `R/1700-F-owner-actions.md` — prior scoped repair actions; CAU consumer-binding portion is updated by the 3afb receipt above.
- `implementation-handoffs/F/family-layout-consumers-20261006.json` — Fry candidate, family/layout checks, monitor-doc equivalence and scoped limitations.
- `implementation-handoffs/F/causal-consumer-boundaries-continuation-20261006.json` — exact CAU candidate, checks, property, and explicit PDC/authority limitations.
- `implementation-handoffs/F/causal-consumer-boundaries-continuation-20261006/cau/root-causal-consumer-independent-review.json` and its `root-input-views-independent3af-*` / `root-diagnostic-independent86-*` companions — independent property, negative-control, removal, and oracle outputs.
- `implementation-handoffs/F/did-selected-cohort-20261006.json#/per_finding/LA-016`, `did-diagnostic-basis-20261006.json#/per_finding/LA-016`, `did-diagnostic-basis-20261006/original-criteria-reconciled.json#/LA-016`, and `cau-cohort-admission.json#/residual_map/10` — unresolved status/source conflict.
