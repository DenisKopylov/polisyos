# DS10 capability discovery — C00 execution journal

## Execution identity and boundary

- Attached branch: `codex/ds10-capability-discovery-plan`.
- Execution base: `8f760b813`.
- Product-root coordinate: `git rev-parse --show-prefix` returned `policy-engine/`.
- C00 mechanism paths: **0/50 observed**. C00 changed only P39 companions.
- C00 widening rounds: **0/12**. Its one register/test transaction adds no
  capability, surface, permission, or producer arm.
- Pattern pass: P35 requires the two complete-set derivations below; P38 keeps
  the DS8 assignment metric at 217 separate from the 261 live roots; P39 excludes
  the required journal, debt/register ledger, and moved denominator pin from the
  mechanism cap; P41 records the upstream missing witness as `artifact_missing`,
  rather than attributing a DS10 implementation failure to it.

## Entry census — two independent derivations

| fact | derivation A | derivation B | observed result |
| --- | --- | --- | --- |
| capability manifest physical lines | `wc -l src/polisyos/runtime/http/services/control/capabilities.py` | `awk 'END {print NR}'` and `git show HEAD:policy-engine/src/polisyos/runtime/http/services/control/capabilities.py \| wc -l` | 267 / 267 / 267 |
| direct `CapabilityFeatureInfo` constructors | AST direct-call walk | tokenizer `NAME CapabilityFeatureInfo` immediately followed by `(` | 21 at `52,59,68,75,84,94,101,108,115,124,131,140,147,154,164,174,184,191,198,206,213` |
| posture constants | quoted-string `git grep` over tracked `src/` | AST constants over all 2,576 tracked Python paths | `discoverable`: 1; `executable`: 2; `admitted_authority`: 2. The files are respectively `pre_adapter_grounding_inventory.py`; that file plus `workspace/loop.py`; and that file plus `legal_mandate_search.py`. |
| live register / DS8 assignment sub-register / DS10 roots | Python JSON length and distinct-set walk | `jq` length/`unique` projections | 261 entries / 261 unique `unit_id`; 217 assignments / 217 unique paths; 10 DS10 roots / 10 unique `unit_id`. Known members: `route-welcome`, `BureaucraticArtifactView.a11y.test.tsx`, and `route-knowledge`. |
| adapter artifact family | five admission JSON inputs plus five contract TOMLs | lifecycle-owner declarations plus G0 readiness manifest | 10 artifacts. |
| admission rows | recursive Python JSON-object walk on `admission_state` | recursive `jq` object walk on `admission_state` | 61 rows: 8 admitted, 52 candidate, 1 blocked; known admitted `layer3-substrate-data-binding-to-source-contract`. |
| declared adapter paths | `tomllib` count partition | TOML `[[adapter_paths]]`, reference, and count-field census | 41: G1 2, G2 4, G3 6, G4 11, GL 18; known `layer3_data_asset_port_to_source_contract`. |

## C00 RED receipts

All selected tests collected successfully and then failed for the intentionally
unimplemented behavior (each exit 1, not a collection/syntax error):

```text
uv run pytest tests/unit/runtime/quality/test_capability_discovery.py::test_capability_discovery_postures_use_three_independent_producers -q
FAILED ...::test_capability_discovery_postures_use_three_independent_producers
Failed: DS10 C01 missing: no capability-discovery composer proves three independent producers

uv run pytest tests/repo_quality/tools/test_ds10_capability_discovery_strangle.py::test_control_capability_manifest_has_no_authored_feature_rows -q
FAILED ...::test_control_capability_manifest_has_no_authored_feature_rows
Failed: DS10 C01 missing: control capability manifest still has authored feature rows

uv run pytest tests/repo_quality/tools/test_ds10_capability_discovery_strangle.py::test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches -q
FAILED ...::test_capability_menu_rejects_hardcoded_picker_rows_and_id_branches
Failed: DS10 C01 missing: capability menu has no generic picker strangle
```

The compulsory denominator pin was also RED after the debt row was added:
`test_real_census_replays_published_invariants` reported `assert 60 == 59`.
That is the expected P39 companion failure; the frontend metric remains pinned
at 217.

## Upstream registry receipt

```text
uv run pytest tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation -q
ERROR: file or directory not found: tests/unit/runtime/quality/test_adapter_registry_free_growth.py::test_post_g0_registry_admits_new_contract_from_data_only_mutation
```

The command exited 4. The absent file is `artifact_missing`, owned by
`team-architecture` with producer lane `runtime/quality`, under debt
`ds10-adapter-registry-data-only-free-growth`. It is not a DS10 RED conjunct and
does not establish authority.

## C00 command ceilings and uptime

| command | uptime before → after | observed terminal / ceiling | writes |
| --- | --- | --- | --- |
| three individual DS10 RED witnesses | `17:28 up 1 day, 7:41` → same minute | completed exit 1 / 300s focused backend ceiling | no |
| upstream data-only registry witness | `17:28 up 1 day, 7:41` → `17:28 up 1 day, 7:42` | completed exit 4 / 300s focused backend ceiling | no |
| debt writer | `17:34 up 1 day, 7:47` → same minute | completed; 240s writer ceiling | yes, canonical `LEDGER.md` only |
| debt report-only | `17:34 up 1 day, 7:47` → same minute | completed; 30s report-only ceiling | no |
| denominator behavioral pin | `17:34 up 1 day, 7:47` → same minute | 1 passed; 300s focused backend ceiling | no |

The report-only output had exactly ten inherited
`register_supplies_missing_standing` findings and one inherited
`register_withholds_source_standing` finding. It had zero render, denominator,
closure, or DS10 debt drift. The writer preserved the checker frontend metric and
denominator at `frontend_disposition_rows=217`; only register `59 → 60` moved.

## Cluster continuation table

| cluster | status | mechanism paths | widening rounds | committed receipt |
| --- | --- | ---: | ---: | --- |
| C00 | ready to commit — attached-branch readback pending | 0/50 | 0/12 | pending |
| C01 | not started | — | — | — |
| C02 | not started | — | — | — |
| C03 | not started | — | — | — |
| C04 | not started | — | — | — |
| C05 | not started | — | — | — |
| C06 | not started | — | — | — |
| C07 | not started | — | — | — |

## Committed-branch readback receipt

The C00 commit is read back from attached
`refs/heads/codex/ds10-capability-discovery-plan`, not from staging. Its exact
eight-path set is the P39 companion set recorded at the top of this journal:
the DS10 plan, debt register, canonically generated ledger, this journal, two
DS10 RED shells, debt-ledger behavioral pin, and checker denominator constant.
`git show --format= --name-only HEAD` and `git show HEAD:<path>` are rerun after
the final amendment; branch attachment and a clean tree are required before
handoff. No committed path is a production mechanism path under `src/` or
`apps/runtime-dashboard/src/`.
