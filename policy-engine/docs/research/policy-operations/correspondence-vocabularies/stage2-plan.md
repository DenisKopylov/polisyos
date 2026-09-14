# Stage 2: expose recomputable AQ1 refusals through DS15

Status: accepted bounded design; Stage 1 committed and read back from the branch before implementation began. This closes one ready production bridge. It does not appoint semantic vocabulary owners or close the entire acquisition union debt.

## Property and boundary

An operator supplies an explicit `NonDataRequest`, an explicit existing `AcquisitionGap`, and a route ID from the canonical N13a census. The existing canonical planner and Fabric AQ1 owner produce and persist a candidate receipt. DS15 consumes a content-bound, independently recomputed refusal for that exact route. Adding dataset rows does not resolve the missing non-data object or enable acquisition action.

The public projection has no receipt, CAS, tenant, or filesystem path parameter. Its sole extra source family lives below the configured governed artifact root. It never reads a private run CAS. Source admission binds the complete census bytes, the complete selected route object, claim, gap, planner report and receipt. Neither `missing_link` nor a route name supplies the semantic demand.

Relevant patterns: P01/P02/P03 (producer, bridge and surface), P05/P15 (candidate remains non-authoritative), P27 (reuse AQ1 and DS15), P29/P32 (run the actual verifier), P35 (complete input denominator), P37/P38 (content/recomputation rather than declarations). Before implementation the ready link is `bridge_missing`/`surface_missing`; this slice's acceptance signal is operator input → real planner → persisted AQ1 receipt → `GovernedProjectionService.get(ACQUISITION_GROWTH)` → existing structural route fields with blocked action, including negative probes.

## Mechanism paths and assignment

1. `src/polisyos/runtime/quality/non_data_acquisition.py` — row-ownership agent. Extend the existing bridge with a runnable operator CLI, strict internal bundle models, source admission and canonical receipt loader. Reuse `run_non_data_acquisition`, `NonDataAcquisitionRuntime`, `FileSystemCAS`, planner load/recompute, Fabric atomic writes/lock. Do not create a second classifier or planner.
2. `src/polisyos/runtime/http/services/acquisition_surface_projection.py` — root. Accept the loader's verified records and project them into the existing `StructuralRouteProjection` fields. Preserve complete acquisition types, resolution state and refusal reasons; action remains `blocked`. Unknown shape stays `not_established` rather than being promoted to an established structural class.
3. `src/polisyos/runtime/http/services/governed_projections.py` — root. The acquisition-growth loader optionally reads the fixed source family, incorporates its complete byte bindings, and supplies verified records to the projector. No bundle preserves the existing historical projection; a present invalid/unverifiable bundle fails the existing packet closed.
4. `src/polisyos/runtime/http/services/governed_projection_validation_worker.py` — root. Independently reread/reverify the source family in `_acquisition_growth_inputs`, add exactly its dependencies to the component denominator, and recompute the emitted payload. Existing exact-set/payload comparisons at `_validate_acquisition_growth_projection` remain decisive.

Mandatory companions are this plan, journal/receipts, mirrored behavioral tests and any actual boundary-registration adjustment required by the existing guards. They are outside the mechanism-path count (P39). No frontend, public DTO, OpenAPI or generated TypeScript field changes are planned: `route_class`, `witness_kind`, `missing_link`, `gap_class` and `action_eligibility` already reach `AcquisitionRouteDetail`.

## Fixed source family and producer

Relative to `POLISYOS_GOVERNED_ARTIFACT_ROOT` (or an explicitly supplied operator governed root):

- Census: `architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json`.
- Bundle: `architecture/policy_design_case/gy_aq1_non_data_projection/receipt-bundle.json`.
- Dedicated CAS root: `architecture/policy_design_case/gy_aq1_non_data_projection/cas`.
- Candidate process journal: `architecture/policy_design_case/gy_aq1_non_data_projection/events.jsonl`.

This runtime root must be a dedicated artifact snapshot outside the repository's
checked `architecture/policy_design_case` output tree. The existing generated-public
lifecycle audit recursively accounts for that tree even when Git ignores files;
repo-root publication would require a separate registration, outside this lane's
no-register-edit scope. No runtime bundle is committed by this lane.

The operator command is `python -m polisyos.runtime.quality.non_data_acquisition --governed-root ROOT --request REQUEST.json --gap GAP.json --route-id ID --run-id ID --at ISO8601`. Input JSON paths are local operator inputs, never HTTP parameters. The CLI returns the emitted bundle/receipt identity; it is a real non-test caller of `run_non_data_acquisition`. Publication is an atomic, locked update of the fixed bundle, keyed by route ID; existing entries must remain valid before replacement. No committed sample bundle asserts a live receipt.

Internal strict bundle schema `policyos.runtime.non_data_refusal_bundle.v1`: entries. Each entry contains `route_id`, canonical selected route SHA256, the explicit typed `gap`, `run_id`, and `receipt_ref`. The receipt already binds request, demand, evaluation time, candidate/vocabulary refs and planner report ref. No stored projection labels or claimed authority are admitted. Duplicate route IDs refuse the bundle. The complete current census bytes enter the loader/service component identity; they are not a frozen bundle field. This property-based correction allows unrelated census row growth without reminting semantic demand, while any selected-route content change refuses until that route is explicitly replaced. Existing retained entries are verified against the current source before atomic publication; replacing a stale selected entry does not require trusting it.

Before producer writes or loader reads, resolve the explicitly configured root as the trusted root and reject every symlink descendant, including dangling links. Apply the same invariant to canonical CAS artifact read/write paths, not only the bundle path. This closes review finding S2-RV02: confinement somewhere inside the governed root allowed the fixed family or CAS to alias a private sibling directory. Artifact refs are typed SHA256 identities resolved only by this family's CAS. Every attempted referenced input must be local to this namespace; a foreign CAS is never opened. The planner report must load and recompute from the bundled gap/run ID and receipt time, and match the receipt/request report refs, instead of treating report-ref presence as planner proof.

## Shared loader interface

The agent provides this API in the existing quality module for root's integration:

```python
@dataclass(frozen=True)
class VerifiedNonDataRoute:
    route_id: str
    receipt: NonDataReceipt

@dataclass(frozen=True)
class NonDataProjectionSource:
    routes: tuple[VerifiedNonDataRoute, ...]
    component_bindings: tuple[tuple[str, str], ...]  # root-relative path, sha256:hex

def load_non_data_projection_source(
    *, governed_root: Path, census: Mapping[str, object]
) -> NonDataProjectionSource: ...
```

Absent bundle returns empty tuples. Present invalid input raises `ValueError` (IO errors are translated to a source refusal). `component_bindings` includes bundle bytes and every successfully read CAS blob/manifest, including the planner report and any candidate/vocabulary actually consulted. Missing dependencies must not silently become a verified projected admission refusal: unresolved dependency reads reject the source family, preventing an absent-to-present transition from escaping the bound denominator. The existing worker tracker separately records implementation and absent-source dependencies, invalidating cached validation when a previously absent bundle appears. The HTTP loader should reread returned components through its existing stable observation path and require the identities still agree before emitting its `_LoadedSource`.

## Generic refusal scope

Only a persisted receipt whose complete result recomputes with the canonical portless AQ1 owner may be projected. This naturally includes `shape_not_established`, `split_required` and `admission_refused` where all referenced inputs resolve and recomputation agrees. Preserve all reason codes and acquisition types; do not branch only on `non_data_object_missing`. Positive or provisional reentry requiring external verifier ports, fabricated outcomes, changed input bytes and any receipt that cannot reverify refuse projection. No semantic vocabulary, signer, external act, or authority is invented to make a receipt pass.

## Verification and stopping boundary

- Producer/loader mirrored tests run the real CLI/main, canonical planner, CAS and receipt reader. Assert exact source-route claim/gap binding and complete dependency identities.
- Service integration runs `get(ACQUISITION_GROWTH)` with the real extra-source loader and worker recomputation. Existing structural UI fields must contain the verified type/state/reasons and blocked action.
- Negative cases: unknown shape; compound demand/split; independent admission refusal; changed request claim or gap; wrong census/route content identity; malformed or foreign receipt; CAS blob/manifest mutation; missing referenced CAS input; previously absent bundle appearing; externally admitted/reentry receipt that cannot reverify portlessly.
- Row-growth falsifier: increase declared dataset row counts while keeping the selected route and non-data demand; refusal/action state must not advance. Changing selected-route content requires the operator producer to run again; its stale route binding itself refuses the projection.
- Run focused tests, lint and affected architecture/source-family guards. Capture a removal probe that disables canonical receipt verification while retaining receipt-shaped markers; the behavior test must fail. Freeze source before independent review, then run the agreed checks once.

The simpler alternative, persisting rendered refusal labels, lacks canonical recomputation and duplicates the source of truth. Merely adding a detached export helper lacks the production caller. Both fail this slice's acceptance property. Broader vocabulary meaning, semantic appointments and successful non-data acquisition/reentry remain with their named AQ1/semantic owners; this slice exposes only the existing recomputable refusal process.

Incidental documentation destination: the worker module docstring describes blanket isolation of heavy owners from the HTTP process, while `governed_projections.py` already imports `runtime.quality.confidence_ledger` and `runtime.quality.design_problem` at module scope. Root inspection confirmed that the new shared loader does not introduce the quality package's eager initialization for the first time. This is a bounded existing documentation discrepancy assigned to the governed projection maintainer; no unrelated import refactor belongs to this bridge.

The import-boundary pass derives the added edges from all four mechanism Python
files using the actual guardrail helper. Existing Core/Fabric/PDC public facades
supply the same CAS and atomic IO owners. Route hashing uses PDC's recorded-content
owner over the whole finite JSON object: unlike `gy_content_hash`, it must preserve
`*_at` fields. The internal hash rule is explicit, Unicode changes invalidate the
binding, and NaN/Infinity refuse before publication. No facade, baseline or export
registry is extended to fit the implementation.
