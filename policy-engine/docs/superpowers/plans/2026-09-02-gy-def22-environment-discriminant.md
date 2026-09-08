# GY-DEF22 Foundry Environment Discriminant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox
> (`- [ ]`) syntax for tracking. **This document is awaiting ratification; Task S stops before
> implementation.**

**Goal:** Close GY-DEF22 by making the Foundry-derived N8 dependency discriminant reconstructible,
shared, and self-describing while explicitly making ambient environment compatibility
non-decisive for N8, N10a, and chronology authority decisions.

**Architecture:** Extend the landed Foundry catalog/discovery candidate reducer with a
dependency-only discriminant that is computed from an admitted root, extras, markers, tracked
`pyproject.toml`, and `uv.lock`. Persist that discriminant in one N8-produced, Foundry-owned
companion artifact. N8, N10a, chronology replay, and the governed machine projection all consume
that exact artifact. Each consumer may report a generic ordered incompatibility diagnostic, but a
strict authority boundary prevents the diagnostic from changing a governing result.

**Tech Stack:** Python 3.14, uv 0.9.21, strict/frozen Pydantic DTOs, domain-separated canonical
digests, TOML owner registries, pytest, Ruff, generated-artifact governance, FastAPI/OpenAPI and
the generated TypeScript runtime clients.

**Spec:** `docs/superpowers/specs/2026-08-20-gy-n12-epoch-chronology-closure-basis.md`
section I; `docs/plans/active/layer3-slices/GY-engine-subordination.md` GY-DEF22; GY-DEF14's
two-close ruling.

## Global constraints

- This Task S deliverable is plan-only. Do not write implementation source until the plan is
  ratified.
- Do not edit `docs/plans/active/`; the architect transcribes the implementation result later.
- Do not modify `src/polisyos/runtime/quality/`. The live GY-PR1a lane owns that package. The
  selected design does not require a change there; discovery of a real requirement there is a stop,
  not permission to route around the owner.
- Do not read, write, relink, or change permissions on `production_data`. GY-DEF22's discriminant
  is dependency-only. The existing production-data manifest remains a separate authority input.
- Preserve the production Foundry authority result:
  `owner_enforced_runtime_subtree_cutoff_not_established`, persistence `not_established`, and
  capability label `producer_missing`. This plan does not invent the missing cutoff, receipt store,
  platform toolchain admission, or production-data trust policy.
- No task-local identity, machine path or machine hash, package allowlist, backend ignore,
  caller-selected profile ID, shell `torch` branch, shaped installed-distribution assertion, or
  prose-only environment description may influence the result.
- A profile label is display/provenance only. Verification must recompute the root and complete
  selected distribution closure from owner data.
- Keep the comparison generic over the resolved closure. An incompatibility outside that closure
  is irrelevant; an incompatibility inside it is reported by a deterministic first-case rule.
- Use only exact pytest nodes and changed Python files during iteration. Freeze source and reviews
  before any expensive replay; never run a directory-wide test command.
- Run the bound debt checker exactly once after the implementation tree is quiescent, with output
  redirected as prescribed by the task that executes this plan.

---

## Decision: choose the explicit non-decisive close

GY-DEF14 permits either recording an authority-grade discriminating input or explicitly declaring
that the ambient block is non-decisive by construction. Choose the second close.

The decisive alternative is not honest on the present repository. The Foundry authority registry
records all four capabilities needed to turn a runtime observation into authority as
`absent/unallocated`:

1. `owner_enforced_runtime_subtree_cutoff`;
2. `owner_resolved_resolution_receipt_store`;
3. `platform_toolchain_admission`;
4. `production_data_trust_policy`.

Promoting the two existing candidate walks would repeat P37: a recomputed observation would carry
an authority-grade gate without a writer-independent cutoff. Building those four capabilities is a
new sovereign subsystem, not the smallest GY-DEF22 repair.

The selected close instead fixes the actual P38 divergence. The intended property is whether N8's
governing evidence and replay are valid. Current behavior can turn on the package posture of the
interpreter running the checker, which is only a proxy for that property. The repaired system makes
the posture useful for diagnosis but structurally incapable of deciding N8 admission, N10a gap
closure, chronology acceptance, publication, or promotion. This is an explicit semantic ruling,
not a silent weakening.

The implementation therefore produces two independent outcomes:

- `diagnostic_verification.status = pass | fail`, with a deterministic first incompatibility; and
- the existing governing N8/N10a/chronology result, computed without consulting that status.

For CB-I02 and CB-I02A, “fails” means the diagnostic verification is `fail`. The governing result
must remain byte-equivalent to the result produced with the diagnostic removed. A test must prove
both halves.

## Current repository readout at `071cf3c5f`

The implementation is not absent in the literal sense, but the capability chain is incomplete.
Commit `f2c202997` landed strict Foundry candidate types, registries, generic lock-graph resolution,
environment-receipt reconciliation, a production preflight refusal, and candidate-level tests.
Commit `911657027` merged that work while explicitly retaining GY-DEF22 as `producer_missing`.

The useful pieces to reuse are:

- `src/polisyos/foundry/methods/catalog/dependency_profile.py` derives a complete selected lock
  closure from root + extras + PEP 508 markers and reconciles only selected names;
- `architecture/production_quality/method_catalog_dependency_profiles.toml` and
  `method_catalog_dependency_authority.toml` own the purpose/profile relation;
- `tests/unit/foundry/methods/test_dependency_profile.py` already has partial semantic witnesses
  for a novel profile, an in-closure substitution, a research-shaped mismatch, and an
  out-of-closure package;
- `tools/quality/validation/check_layer3_gy_value_gate_contract.py` already separates
  `governing_issues` from `ambient_findings`;
- `tools/quality/validation/check_layer3_gy_second_domain_pack.py` already preserves the exact N8
  authority non-receipt instead of inventing a local cause; and
- `tools/quality/validation/execute_gy_n12_artifact_transition.py` already has candidate/readback
  seams for N8, N10a, and chronology.

What is still missing is the actual GY-DEF22 chain: no persisted dependency discriminant, no N8
producer for it, no shared N10a/chronology read, no exact CB-I01–CB-I03A end-to-end semantic suite,
and no machine/audit surface. The honest current state remains:

```text
producer_missing + artifact_missing + semantic_test_missing + surface_missing
```

Two additional current-state facts must be handled rather than hidden:

- the tracked profile declares pyproject domain digest
  `sha256:57498f29ef1e6b6bf8f7edf3fbe03573686b64d2c0d72077eac9edc3b3223efb`, while
  the current tracked `pyproject.toml` recomputes to
  `sha256:803cbfb79c7727807db1c98d07413e8ef2f1b2a08929bd99bc2f8e638ee5142d`;
  the `uv.lock` domain digest still matches its declaration. The owner row must be regenerated and
  rebound from current tracked bytes, never patched by hand in a test.
- the committed N8 v2 artifact is the legacy positive-shaped packet, while the current public
  `build_payload()` deliberately produces the typed `producer_missing` non-receipt. GY-DEF22 must
  not use an environment field to bless either shape or broaden this task into the N8 transition.
  The discriminant is a separately registered companion bound to the exact N8 artifact bytes.

The Task S research environment was provisioned with:

```bash
uv sync --frozen --extra test --extra runtime --extra research
```

The installed metadata reports `torch==2.10.0`, reproducing the historical research-profile
condition without consulting `production_data`.

## Acceptance basis — quoted exactly

The implementation must discharge these five clauses exactly as written in the ratified closure
basis:

> - **CB-I01 — admitted profile identity:** deployment records bind a
>   reconstructible dependency profile/root/distribution discriminant shared by
>   N8, N10a and chronology replay, while the Foundry catalog/discovery boundary
>   remains its authority owner.

> - **CB-I02 — research-profile regression:** the documented research environment
>   with `torch==2.10.0` fails and names the decisive discriminant as the first
>   case, never as a special profile/package rule.

> - **CB-I02A — name-invariant incompatibility:** hold the profile label and
>   shaped record constant, substitute an incompatible distribution inside the
>   resolved deployment closure and recompute the discriminant; verification
>   fails. A second incompatible profile generated from data fails without a
>   known-name allowlist or code edit.

> - **CB-I03 — irrelevant difference:** a package difference outside the resolved
>   deployment closure does not fail the replay.

> - **CB-I03A — novel admitted profile:** a novel admitted profile/distribution
>   derives its discriminant and dependency closure from recorded data and
>   verifies without a code edit, machine pin or known-package allowlist.

## The one shared artifact

Add one registered generated-committed artifact:

```text
architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json
```

The Foundry catalog/discovery module owns the schema and derivation. The N8 tool is the producer.
N10a, chronology replay, and the governed machine projection must read these exact bytes; none may
copy the distribution list or independently select a profile.

The strict v1 statement records:

```json
{
  "schema_version": "polisyos.foundry.n8_dependency_discriminant.v1",
  "rule_version": "polisyos.foundry.dependency_discriminant.v1",
  "produced_by": "tools.quality.validation.check_layer3_gy_value_gate_contract",
  "authority_owner": "polisyos.foundry.methods.catalog",
  "authority_purpose": "n8_method_catalog_reconstruction",
  "source_freeze": "<40-hex commit>",
  "n8_contract_ref": {
    "path": "architecture/policy_design_case/layer3_gy_value_gate_contract.json",
    "schema_version": "<recorded N8 schema>",
    "rule_version": "<recorded N8 rule>",
    "content_hash": "sha256:<exact N8 bytes>"
  },
  "profile_discriminant": {
    "profile_id": "<display identity; never a gate>",
    "declaration_ref": "<domain-tagged ref>",
    "root_distribution": "policy-engine",
    "extras": ["<sorted owner data>"],
    "python_constraint": "<owner data>",
    "resolver_name": "uv",
    "resolver_version": "0.9.21",
    "pyproject_ref": "<domain-tagged digest>",
    "lockfile_ref": "<domain-tagged digest>",
    "marker_environment": [["<used marker>", "<value>"]],
    "resolved_distributions": [
      {
        "name": "<normalized name>",
        "version": "<resolved version>",
        "source_kind": "<resolved source kind>",
        "selected_artifact": "<domain-tagged digest>"
      }
    ],
    "distribution_set": "<domain-tagged digest>",
    "discriminant_ref": "<domain-tagged content ref>"
  },
  "predicate_class": "recomputed",
  "decision_role": "ambient_non_decisive",
  "authority_boundary": {
    "authoritative_for": ["dependency_environment_diagnosis"],
    "may_not_use_for": [
      "n8_admission",
      "n10a_stage_gap_closure",
      "chronology_acceptance",
      "policy_publication",
      "policy_promotion"
    ]
  },
  "artifact_content_hash": "sha256:<canonical statement>"
}
```

Use a new digest domain for `discriminant_ref`, registered in
`method_catalog_dependency_digest_domains.toml`; do not overload the existing
`dependency-closure` domain. The existing closure includes the production-data manifest, while this
artifact deliberately proves only dependency selection. Reusing that digest would conflate two
different preimages and violate the task's data boundary.

The artifact records no absolute interpreter path, host name, machine identifier, installed
environment path, or production-data reference. A consumer computes an ephemeral strict
`DependencyEnvironmentDiagnosticResult` from its own interpreter and the frozen discriminant. The
result contains `status`, `ordered_cases`, and `first_case`; it is emitted in command/audit output,
not written back into the shared artifact.

Verification has two deliberately separate levels. Artifact replay recomputes the complete locked
rows, including `selected_artifact`, from tracked owner data and therefore rejects a same-version
lock/source substitution. Runtime diagnosis compares only independently observable installed
coordinates (normalized name and version, plus source identity only when a real Foundry receipt
supplies it). It must never infer a selected artifact merely because an installed version matches a
lock row. Missing source evidence is a typed `not_established` diagnostic limitation, not a guessed
pass and not a governing failure. The historical research fixture fails earlier on the independently
observable `torch` version coordinate.

Case ordering is part of the rule version:

1. root-distribution disagreement;
2. missing resolved distribution, sorted by normalized name;
3. version/source/selected-artifact disagreement, sorted by normalized name and field;
4. unexpected in-closure identity.

Each case carries a generic coordinate such as `distribution:torch:version`, expected value,
observed value, and predicate class. There is no branch on `research`, `torch`, backend name, or a
known profile ID.

## Derivation and consumer flow

```text
Foundry purpose admission + tracked source freeze
  -> profile declaration (root/extras/markers)
  -> generic uv.lock graph walk
  -> sorted resolved distribution closure
  -> N8-produced discriminant artifact
     -> N8 ambient diagnostic
     -> N10a ambient diagnostic (same artifact bytes)
     -> chronology replay ambient diagnostic (same artifact bytes)
     -> governed machine/audit projection (same artifact bytes)
```

Derivation is data-based, not declaration-based, in the P38 sense:

1. The caller supplies only `n8_method_catalog_reconstruction` and a source freeze.
2. Foundry resolves purpose -> profile from its authority registry and verifies the declaration ref.
3. It reads exact `pyproject.toml` and `uv.lock` bytes at that source freeze, recomputes both domain
   digests, parses root/extras, walks every selected dependency edge, evaluates only marker keys that
   influence the walk, and sorts the complete closure.
4. It hashes the complete distribution rows and the composite profile/root/marker/distribution
   statement. The profile label is recorded but never consulted after owner resolution.
5. A consumer observes installed distributions generically through Python distribution metadata,
   projects only names in the resolved closure, and recomputes comparison cases. Packages outside
   the closure may be counted for audit but cannot enter `status` or `first_case`.
6. N8, N10a, and chronology verify the artifact's content hash, N8 binding, source freeze, schema,
   rule, and authority boundary before reporting the same diagnostic. An invalid artifact is a
   diagnostic non-receipt; it still cannot become a governing failure or pass.

Factor this dependency-only derivation out of the existing
`resolve_dependency_profile()` before its production-manifest predicate. The current authority path
then composes the dependency discriminant with the production manifest exactly as before. This
preserves the authority refusal and avoids a second resolver.

## Red-first acceptance map

Write all five tests before implementation and run only these exact nodes. The test name is the
acceptance ID; partial pre-existing tests remain useful helpers but do not substitute for these
end-to-end witnesses.

| Acceptance | New red-first test | Required observation |
| --- | --- | --- |
| CB-I01 | `tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant` | N8 produces one strict artifact; N10a and chronology independently read the same content ref and reconstruct the same profile/root/distribution rows. |
| CB-I02 | `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case` | Resolve the documented `research` extras from tracked data; the generic diagnostic is `fail`, and the first coordinate is the data-derived `distribution:torch:*`. No production code contains a `torch` or `research` branch. |
| CB-I02A | `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities` | Hold label and DTO shape constant, mutate one selected lock row, then resolve a second incompatible TOML profile; both recomputations fail without a code edit or allowlist. |
| CB-I03 | `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant` | Add/change an installed package absent from the selected closure; status and first case remain identical and passing. |
| CB-I03A | `tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data` | Append a novel owner-registry row in scratch, derive its closure and matching observation, and verify without changing Python code or using machine identity. |

Also add three structural falsifiers after the acceptance reds:

- remove the distribution comparison while retaining schema/field markers; CB-I02A must fail
  (`P29`);
- make `diagnostic_verification.status` govern N8, N10a, or chronology while keeping the artifact
  valid; the authority-boundary test must fail (`P38`);
- feed the same shaped observation under a renamed profile and under a second novel profile; the
  outcome must follow recomputed closure content, not the label (`P33`).

Initial red command:

```bash
PYTHONPATH=.:src uv run --frozen --extra test --extra runtime --extra research pytest -q \
  tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py::test_cb_i01_n8_n10a_and_chronology_share_one_foundry_discriminant \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02_research_profile_names_torch_as_first_generic_case \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i02a_label_and_shape_cannot_mask_two_data_generated_incompatibilities \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03_outside_closure_difference_is_diagnostic_irrelevant \
  tests/unit/foundry/methods/test_dependency_profile.py::test_cb_i03a_novel_admitted_profile_verifies_from_owner_data
```

Expected initial failures are missing DTO/producer/consumer behavior. Import errors, collection
errors, skips, or failures caused by `production_data` are harness failures, not acceptable RED.

---

### Task 1: Establish the five acceptance reds

**Files:**

- Modify: `tests/unit/foundry/methods/test_dependency_profile.py`
- Modify: `tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py`

**Interfaces:** consumes the ratified CB-I01–CB-I03A clauses; produces one exact semantic test per
clause plus reusable data-driven fixtures.

- [ ] Add the five tests with the exact names and observations in the acceptance map.
- [ ] Build research and novel-profile fixtures by parsing tracked TOML/lock data. Test code may
  assert the historical expected coordinate `torch`; production code may not name it.
- [ ] Run the five-node command and retain every RED. Confirm no skip and no dependency on
  `production_data`.
- [ ] Add the P29/P33/P38 structural falsifiers and run only their exact nodes to RED.

### Task 2: Factor the Foundry dependency-only discriminant

**Files:**

- Modify: `src/polisyos/foundry/methods/catalog/dependency_evidence.py`
- Modify: `src/polisyos/foundry/methods/catalog/dependency_profile.py`
- Modify: `src/polisyos/foundry/methods/catalog/README.md`
- Modify: `architecture/production_quality/method_catalog_dependency_digest_domains.toml`
- Modify: `architecture/production_quality/method_catalog_dependency_profiles.toml`
- Modify: `architecture/production_quality/method_catalog_dependency_authority.toml`
- Modify: `tools/devx/foundry/sync_dependency_profile.py`

**Interfaces:** consumes owner purpose, source freeze, registry data, tracked dependency bytes, and
an installed-distribution observation; produces a strict dependency discriminant or one typed
diagnostic non-receipt. It does not produce authority admission.

- [ ] Add the new digest domain and strict/frozen discriminant, observation, case, and result DTOs.
  Use discriminated unions and `extra="forbid"`; every public function gets a Google-style
  docstring and complete annotations.
- [ ] Extract `resolve_dependency_discriminant()` from the existing lock-graph walk. Make the
  current `resolve_dependency_profile()` call it, then add the production-manifest relation exactly
  as today. Prove existing authority failures and closure bytes are unchanged for unchanged inputs.
- [ ] Add a generic installed-distribution observer. Normalize names with the existing canonicalizer;
  derive its complete comparison population from the resolved closure, not an enumerated package
  set.
- [ ] Add deterministic reconciliation and first-case ordering. Return all cases for audit while
  making `first_case` the first element by construction.
- [ ] Extend the existing Foundry sync tool with a read-only `diagnose` mode. Preserve the current
  `sync` preflight refusal and its no-write invariant; do not create a local authority substitute.
- [ ] Regenerate the tracked profile declaration and purpose binding from current tracked
  `pyproject.toml`/`uv.lock` bytes through the Foundry owner tool. Add a corrupt-byte check proving a
  stale row fails closed. Never hand-edit only the stale digest.
- [ ] Run the four Foundry acceptance nodes and the existing exact partial witnesses for novel,
  in-closure, research-shaped, and out-of-closure behavior.

### Task 3: Make N8 produce and validate the shared artifact

**Files:**

- Modify: `tools/quality/validation/check_layer3_gy_value_gate_contract.py`
- Add: `architecture/policy_design_case/layer3_gy_n8_dependency_discriminant.json`
- Modify: `tests/unit/runtime/quality/test_value_gate.py`

**Interfaces:** consumes the Foundry dependency discriminant and exact frozen N8 bytes; produces one
content-bound companion artifact and one ambient diagnostic channel.

- [ ] Add explicit CLI modes to write/check the companion at a supplied path. Candidate writes must
  refuse governed paths unless `--write` is explicit; checks never rewrite.
- [ ] Resolve the profile only from `authority_purpose` and `source_freeze`. Bind the artifact to
  exact N8 bytes, schema, rule, and content hash.
- [ ] Validate strict shape, registered digest domain, closure recomputation, N8 binding, source
  freeze, and the exact `ambient_non_decisive` authority boundary.
- [ ] Feed a current-environment comparison only into `ambient_findings`. Preserve the existing
  governed projection and authority non-receipt byte-for-byte.
- [ ] Add paired tests showing that admitted and research observations produce the same
  `governing_issues`, while the research observation adds the ordered `torch` diagnostic.
- [ ] Add corruption tests for altered root, selected distribution, source freeze, N8 content ref,
  decision role, and `may_not_use_for`. A forged `pass` with mismatching rows must fail validation.
- [ ] Run the exact N8 nodes plus CB-I02/CB-I02A; require no skip.

### Task 4: Wire N10a and chronology to the same bytes without governing on them

**Files:**

- Modify: `tools/quality/validation/check_layer3_gy_second_domain_pack.py`
- Modify: `tools/quality/validation/check_layer3_gy_epoch_chronology_contract.py`
- Modify: `tools/quality/validation/execute_gy_n12_artifact_transition.py`
- Modify: `tests/unit/runtime/quality/test_second_domain_pack.py`
- Modify: `tests/repo_quality/tools/test_layer3_gy_epoch_chronology_contract.py`
- Modify: `tests/repo_quality/tools/test_execute_gy_n12_artifact_transition.py`

**Interfaces:** consumes the exact companion artifact through three independent readers; produces
ambient diagnostics and readback receipts while leaving governing closure unchanged.

- [ ] Give N10a one repository-root reader that validates the companion through the Foundry/N8
  owner API. Return its `discriminant_ref`, status, and first case alongside the existing exact N8
  governing result.
- [ ] Prove a research mismatch no longer becomes `stage_gap_triage_drift` or changes
  `n8_transport_tuple_hardcode` closure. The diagnostic must name the distribution before any
  downstream generic symptom in CLI JSON.
- [ ] Add a chronology `ValidationResult` with separate governing and ambient tuples, retaining the
  existing governing-only wrapper for compatibility. It reads the same companion and never copies
  its closure.
- [ ] Extend transition measurement/readback receipts with the exact discriminant content ref and
  ambient case. Do not change `_N8_ENVIRONMENT_RECEIPT_ADMISSION_STATE`, do not admit a candidate
  receipt, and do not loosen the existing write/attachment gate.
- [ ] Run CB-I01 and exact N10a/chronology nodes. Add a negative where each consumer sees a different
  copied artifact; reconciliation must fail as a binding error, not silently compare copies.

### Task 5: Register and surface the companion

**Files:**

- Modify: `architecture/generated_artifacts.toml`
- Regenerate: `docs/reference/generated-artifacts.md`
- Modify: `src/polisyos/runtime/http/services/governed_projections.py`
- Modify: `src/polisyos/runtime/http/services/governed_projection_validation_worker.py`
- Modify: `tests/unit/runtime/http/test_governed_projection_service.py`
- Modify: `tests/unit/runtime/http/test_governed_projection_validation_worker.py`
- Regenerate through registered owners if the OpenAPI shape changes:
  `schemas/runtime_api_v1.openapi.json`, `packages/runtime-api-client/types.ts`,
  `packages/runtime-api-client/runtimeApiClient.ts`,
  `packages/runtime-api-client/runtimeApiClient.js`,
  `packages/runtime-api-client/canonicalRuntimeApiClient.ts`,
  `packages/runtime-api-client/canonicalRuntimeApiClient.js`, and
  `apps/runtime-dashboard/src/api/types.ts`
- Add: one release fragment under `release-fragments/unreleased/`

**Interfaces:** consumes the validated artifact; produces a registered generated-artifact lifecycle
and a typed machine/audit projection that says exactly what the diagnostic may and may not prove.

- [ ] Register the companion with N8 as generator, Foundry catalog/discovery as semantic owner,
  committed lifecycle, exact write/check commands, stale-output failure, and a freshness rule bound
  to profile/source/N8 bytes.
- [ ] Project the discriminant through the existing `value-gate` machine surface as a related owner
  binding; do not add a second package list or a second profile resolver in Runtime HTTP.
- [ ] Expose `decision_role`, `predicate_class`, `authority_boundary`, profile/root/distribution
  discriminant, and the artifact content ref. Do not expose host paths or promote diagnostic failure
  to source invalidity.
- [ ] Regenerate only owner-declared outputs. If the typed HTTP payload changes, run all three
  registered OpenAPI/client/dashboard generators; never hand-edit generated files.
- [ ] Add a service test that corrupts the related artifact and gets a typed diagnostic non-receipt,
  plus a test that a valid research mismatch remains an available projection with a non-decisive
  `fail` diagnostic.

### Task 6: Integrated targeted verification

**Files:** all Task 1–5 mechanism, test, registered artifact, generated, and release-fragment paths.

**Interfaces:** consumes the frozen implementation; produces evidence for the five clauses, owner
boundaries, artifact lifecycle, and external surface.

- [ ] Run the five-node CB command again and require five passes, zero skips.
- [ ] Run only the exact new P29/P33/P38 falsifier nodes and the exact N8/N10a/chronology/surface
  nodes added by Tasks 3–5.
- [ ] Run the companion's registered `--check`, then corrupt one resolved-distribution field in a
  scratch copy and require the same check to fail. Restore by discarding the scratch copy, never by
  rewriting the governed artifact.
- [ ] Run Ruff only on changed Python files and `git diff --check`.
- [ ] Run architecture guardrails because the digest registry, generated family, tools, and HTTP
  boundary changed.
- [ ] If generated HTTP outputs moved, run the registered OpenAPI verifier, runtime-client verifier,
  and dashboard typecheck using their exact owner commands.
- [ ] Enumerate changed paths and require exact equality with the ratified blast radius. Confirm
  zero paths under `src/polisyos/runtime/quality/` and zero reads/writes under `production_data`.
- [ ] Run the bound debt checker once, redirected to the implementation journal's scratch receipt.

### Task 7: Foundry adjudication, capability accounting, and closeout

**Files:** implementation journal and architect transcription only; no active-plan edit by the
implementer.

**Interfaces:** consumes the frozen diff and verification packet; produces the last required
Foundry owner acceptance and precise register transition.

- [ ] Ask the Foundry catalog/discovery reviewer to accept exactly these claims:
  1. purpose -> profile remains Foundry-owned and callers cannot select an identity;
  2. the dependency-only preimage and new digest domain exclude production data and machine
     identity;
  3. the complete closure and first-case ordering are generic over registry/lock data;
  4. N8 is the sole producer of the registered companion and all consumers verify the same bytes;
  5. ambient diagnostic status is structurally barred from N8 admission, N10a closure, chronology
     acceptance, publication, and promotion; and
  6. the positive authority capability remains `producer_missing` with the four absent owner
     capabilities named, rather than being promoted by this repair.
- [ ] Require an accepted review reference tied to the final source commit. A prose “looks good”
  without commit, artifact, test, and authority-boundary identity is a non-receipt.
- [ ] Record the capability split precisely: the GY-DEF22 diagnostic chain becomes implemented only
  after producer + persisted artifact + N10a/chronology bridges + verification + machine surface +
  semantic tests are present; the separate authority-grade admitted-environment chain remains
  `producer_missing`.
- [ ] Reopen `docs/reference/policy-design-case-failure-patterns.md` and close the P38 pass only after
  proving the governing outcome is invariant to the diagnostic result.
- [ ] Append exact architect transcription prose to the implementation journal and stop for merge.

## Blast radius and collision ruling

The complete tracked literal-reference census at the entry base, excluding planning/history docs,
found these N8 artifact consumers: four committed JSON artifacts, two Runtime HTTP service files,
three runtime tests, and three quality validators. The exact paths are:

```text
architecture/policy_design_case/layer3_gy_depth_n_universality_contract.json
architecture/policy_design_case/layer3_gy_n13a_acquisition_census.json
architecture/policy_design_case/layer3_gy_second_domain_census.json
architecture/policy_design_case/layer3_gy_second_domain_pack.json
src/polisyos/runtime/http/services/governed_projection_validation_worker.py
src/polisyos/runtime/http/services/governed_projections.py
tests/unit/runtime/http/test_governed_projection_service.py
tests/unit/runtime/http/test_governed_projection_validation_worker.py
tests/unit/runtime/quality/test_second_domain_pack.py
tools/quality/validation/check_layer3_gy_depth_n_universality_contract.py
tools/quality/validation/check_layer3_gy_second_domain_pack.py
tools/quality/validation/check_layer3_gy_value_gate_contract.py
```

The census command was:

```bash
git grep -l -I -F \
  'architecture/policy_design_case/layer3_gy_value_gate_contract.json' \
  071cf3c5feab54e57f21f1f931984f4319852536 -- \
  ':!docs/plans/active/**' ':!docs/superpowers/**'
```

The implementation should directly modify only the owner, producer, N10a, chronology, transition,
generated-artifact, and HTTP surface paths enumerated in Tasks 1–5. The four downstream committed
JSON references and the depth-N validator are readback regression consumers: test them if their
semantic projection sees the companion, but do not rewrite them merely to repeat the discriminant.

No required implementation path is under `src/polisyos/runtime/quality/`; GY-PR1a's stop condition
is therefore not triggered by this plan. If implementation review shows that a governing N8 result
can only be made invariant by changing that package, stop and record the collision. Do not weaken
the boundary, copy the logic into a tool, or ask the diagnostic to carry authority.

## Pattern and capability pass

- **P01/P02:** the landed candidate contract is not closure. The target chain is owner reducer ->
  N8 producer -> persisted artifact -> N10a/chronology consumers -> verification -> HTTP/audit
  surface.
- **P03:** the new discriminant is projected through the governed machine surface; it is not hidden
  in a lane journal.
- **P05/P15:** candidate environment observation never becomes authority, publication, or promotion
  evidence.
- **P07:** schema/rule and source-freeze bindings make replay explicit.
- **P10:** the first case names the actual differing coordinate rather than a generic downstream
  mismatch.
- **P13:** the non-decisive close reuses the existing reducer and issue-channel separation instead
  of building four absent authority capabilities.
- **P27:** N8, N10a, chronology, and HTTP do not mint local profile lists; they read the Foundry-owned
  artifact.
- **P29/P33:** semantic mutation tests remove comparison behavior and vary labels/profiles while
  preserving markers.
- **P32/P37:** a shaped record, caller declaration, or repeated scan cannot carry an authority gate.
- **P38:** the ambient proxy becomes diagnostic-only, and a divergent research environment proves
  governing invariance.

Acceptance signal: all five CB-I tests pass with zero skips; the research case names the generic
`torch` coordinate first; two in-closure substitutions fail; one out-of-closure change and one novel
admitted profile pass as specified; all three internal consumers bind one artifact ref; the governed
machine projection exposes the limitation; the production authority still returns its exact
non-receipt; Foundry accepts the frozen packet; and no `src/polisyos/runtime/quality/` or
production-data path is touched.
