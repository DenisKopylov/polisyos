# IR owner/version decisions — red-team R1

## Scope and basis

Reviewed the G architecture brief, draft `01-ir-owner-contract.md` and `02-ir-version-compatibility.md`, the exact Q1/Q2 packet at `f12fb9895a4009ce77828554f4c5c18d83e6ec15`, the accepted ADR-0107 and Rule 12. The packet’s source census is mixed-source and its runtime falsifiers are unrun; this review treats source as static evidence, not runtime proof. No tests, imports, builds, or product edits were made.

**Decision direction is sound:** use one owner-bound read/write admission law, preserve explicit schema declarations, pin migrations and snapshots, and keep the public release-planning compatibility semantics. Two issues still need a sharper implementation boundary: an existing typed loader can currently project generic JSON into a typed DTO without schema-owner admission, and the extension acceptance criterion does not distinguish new resources from new schema/law declarations.

## R1-1 — A real typed consumer still has a generic-read escape

**Severity: blocker for claiming the owner contract is wired. Bucket: same P27/P31/P32/P38 owner-bypass class, deeper existing consumer route (not a new class).**

At the question source, `ABMResultRef` declares `kind="ir.abm_result"` and JSON media but no schema name/version (`refs.py@fb421c0e7175e2119f31a4b5f7bb0aa87966774f:98-102`). The generic read path checks selected-view identity, canonical profile/bytes, and ref `kind`/`media_type`; it does not compare an expected owner schema (`io.py@c3da682f0c6a274dd81abfb05f3f9c59a4bb1192:186-315`). The actual typed route is only:

```python
def load_abm_result(store, ref):
    return ABMResult.model_validate(get_json_artifact(store, ref))
```

(`phase4_dynamics.py@50782e3e5a172770458aa43b0140cef6f5a59326:685-686`). `ABMResult` requires an embedded `schema_version`, `exec_plan_ref`, and `metrics_ref`, but that DTO validation does not bind the manifest’s schema identity (`phase4_dynamics.py@50782e3e5a172770458aa43b0140cef6f5a59326:321-330`).

**Divergent case:** persist canonical, hash-consistent JSON with `kind=ir.abm_result`, `media_type=application/json`, and an unrelated manifest schema identity; give it a payload valid for `ABMResult` (including the required refs). An `ABMResultRef` passes the generic helper’s kind/media checks; generic JSON decoding succeeds; `ABMResult.model_validate` returns a typed result. The artifact is therefore typed despite the expected owner/schema not having admitted it. This is exactly the boundary where a byte/profile-valid candidate must not become an owner-typed input.

Q1’s shared-admission and no-fallback statements (draft 01 L28-30, L40, L64-65) point the right way, but the acceptance plan should name this extant route. Require `load_abm_result` to bind the `ABMResult` owner contract before payload use, compare the exact manifest schema/version and selected profile against that owner snapshot, and carry the admission/source context through DTO construction. Add a wrong-schema/same-kind-and-media negative through this loader, plus a property-removal probe that leaves descriptor fields and DTO shape intact. A generic helper or a correctly-shaped DTO test alone will miss this escape.

## R1-2 — “register extension” can become per-resource capability gating

**Severity: blocker for the universality/free-growth claim unless the terms are separated. Bucket: Rule 12 / capability-gating enumeration, distinct from R1-1.**

Q1 says an extension registers an owner descriptor, exact identity, compatibility rules, and conformance evidence (draft 01 L48); its decisive test first says “Register a supported extension” and then verifies discovery/execution (L66). Nearby prose says discovery finds new methods/data without changing the mechanism (L50). Those statements permit two different implementations: (a) new *schema or semantic law* gets a governed owner declaration, while new resources under an existing adapter/schema are found by search; or (b) every new method/dataset must be entered into a central owner/family registry before it is discoverable. The second is an enumerated capability registry even if represented as configuration, and it makes each resource addition a procedural approval step.

**Divergent case:** add a new dataset/method that conforms to an already-admitted schema and existing adapter. If it is absent from the owner-extension list, does the existing search path still discover and execute it? If not, the claimed free-growth path depends on a per-resource registry update. Rule 12 expressly permits finite schemas/rule versions but requires a correctly added resource to become visible and executable without code change, with frontier/index freshness/recall and a free-growth test (`universal-policy-design-system-vision-and-organizing-rules.md@ace72e4066409340b3367459a4d8e56ccd1b7282:210-230,253-276`).

Smallest repair: state that the owner/compatibility registry governs wire representations and genuinely new semantic laws only. Resource/method/dataset discovery stays on the existing search/adapter path; no per-resource capability entry or approval is required when an admitted adapter/schema already applies. Split Q1 acceptance into (1) a new schema/law registration with reviewed conformance, and (2) two distinct new resources under an existing schema/adapter, discovered and executable with zero dispatch, adapter, family-list, or resource-registration edits; include the declared search frontier and recall/freshness evidence. This preserves review for new executable laws without turning resource growth into a central catalog.

## Compatibility and registry seams to preserve

Draft 02 L11-13 correctly narrows new typed admission without redefining ADR-0107’s public `FULL` promise. Keep this as a purpose boundary over one compatibility source, not a second compatibility catalog. The seam is real: at f12, `_causal_evidence_bundle_version` calls `negotiate_schema_version` in a typed loading path, then `load_causal_evidence_bundle` calls generic `get_json_artifact` (`evidence_bundle.py@832447e9d21200a283e4b7b9b1dc5ffd766dacca:406-437`); `policy_ir.py` registers `policy_ir@1.0` as `FULL` (`@36ce865c83d8284525fe89ac6ff04568a8e529c5:11-20`). ADR-0107 defines FULL as same-major direct readability unless narrowed and defines `negotiate_schema_version` as release-review/migration-planning API (`0107-ir-analytics-normalization-and-schema-compatibility.md@d9a03976fd63c4d0eb7e4d67c09c05a7fe556adf:33-58`).

The draft already calls for routing typed intake through an owner-bound narrower profile while preserving the planning API. Pin that with a paired discriminator: a registered FULL rule still returns its documented planning result, while an owner-typed loader refuses an unknown same-major (and unknown equal) representation before constructing the DTO. Exercise the EvidenceBundle path itself so it cannot keep using the weaker planning answer as admission. This is not a request to globally change historical `FULL` rules or to re-open ADR-0107.

The registry shape is also directionally correct: draft 01 says representation/capability views are generated from the same registry records (L23-26), and draft 02 says that registry is the single compatibility source (L17-19). Preserve that literally: do not add a separately editable owner-family dispatch table beside `base.py`/`schema_registry.py`. The explicit contract-to-key mapping is useful; it must be stored once and any typed-ref view must point to/derive from that record. Exact schemas and semantic laws are legitimate declarations, not evidence that every method or dataset belongs in the registry.

## Other requested dimensions

- **Migration/version behavior:** explicit directional edges, source/target validation, pinned deterministic paths, immutable source representation, conflict refusal, and refusal of unknown equal versions are coherent. Keep the exact-version fast path behind owner/profile resolution as draft 02 L9 requires; the legacy negotiation function’s equality shortcut is not an admission proof (`base.py@a9528432d3d1298b659d8c33237bc52387995e87:117-150`).
- **Rollout/rollback:** reader-first, writer rollback first, preservation of capable readers for already-published new objects, and visible refusal by strict old readers are honest. Acceptance should retain the draft’s after-publication rollback case; no separate blocker found.
- **Cache:** the selected artifact/profile association, owner/validator revision, purpose, and governance/access epoch are appropriate semantic key dimensions. Preserve immutable snapshots and separate historical replay from protected-currentness decisions; no separate blocker found.
- **No hundreds of defaults:** finite, exact owner/schema records are allowed by Rule 12. Avoid seeding defaults from an inferred family/method list; synthesize compatibility and capability only from actual owner records and the search mechanism.

## Pattern pass and closure status

Relevant patterns: P27/P31/P32/P38 (typed-owner bypass and property/implementation divergence), P07 (compatibility-rule replay/API evolution), P13/Rule 12 (registry gravity and capability discovery), and P01/P02/P10 (do not call the design a wired, semantically tested capability). Target pattern: one immutable owner admission record/resolver used by all typed intake routes, legacy release-planning API kept distinct, and resource growth discovered through the existing search/adapter seam. For the proposed owner admission, implementation/bridge/verification/semantic test remain absent from this document review; do not report a product capability as complete. No runtime test status is claimed.
