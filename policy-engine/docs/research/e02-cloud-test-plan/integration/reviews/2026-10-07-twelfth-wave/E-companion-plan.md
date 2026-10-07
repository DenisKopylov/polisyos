# E canonical ABI and public-surface companion plan

**Status: plan only.** No generators, tests, dependency setup, TypeScript scanner,
source edits, or Git operations were run for this task. The B model test owns the
current lightweight compute slot; this plan leaves that slot untouched.

## Pins and ownership

- G integration checkout: `83e7c0e934d0b40644dec8a24264a0602ef013e7`, tree
  `dc1a7697f506b23f2db0f1c80bf929fd2d6a2e0d`; clean and attached to
  `codex/e02-integration` when inspected.
- E source candidate: `717cea243ebac00d41560f90327269a8daec9ef4`, tree
  `ccebb63e9b57f99b0bdaba329e29b0a1c32133d9`.
- `3932cded22a29254a7dfced99723e147d6fea7cb` is an ancestor of `717cea`; the
  intervening E publication is evidence-only (`policy-engine/src` and
  `policy-engine/tools` have no delta). `final-companions.json` records a
  nine-path generated projection for 3932 and its source base
  `64d7444a18c55df7b88b71b7699a2f1b25ca24bd`.
- E owns the finite-ratio law and typed source. G owns only the shared generated
  ABI/public-surface companions. The source packet says `surface_missing`; its
  proposed patch is a projection oracle, **not** an integration-ready patch.
  Do not apply/copy it. Regenerate after the exact E source is accepted into a
  frozen G tree, then compare the resulting path set and bytes with this packet.

The packet's direct patch is
`finite-posterior-law/final-companions/generator-3932cded/canonical-generated-full-final3932.patch`
(`sha256 0afd7b4720f1d92d83524dcd10d7b08de47f7b6254667be1d707a6107e78d69e`).
Its `git apply --check` receipt is from the E author checkout/base, not from G;
it establishes no applicability on G's integration tree.

## Nine generated paths in the owner packet

The hashes below are the packet's expected projection at 3932, not a promise
that the integrated G regeneration will be byte-identical. The schema manifest
contains environment provenance that the canonical checker intentionally
ignores; OpenAPI also binds current source dependencies.

| Generated path | Packet projection SHA-256 | Canonical producer |
| --- | --- | --- |
| `policy-engine/architecture/public_surface/inventory.json` | `1981e8a6905568dac57d86f3ca9d156c077c5e7873a5f9a6ac6ea5553e8bf2a0` | Architecture guardrails / public-surface owner |
| `policy-engine/docs/reference/ir/schema-catalog.md` | `9d370c8a8e324b4ee4d06f27b451596666bab822113aef673953ad5470f31bab` | IR reflection catalog |
| `policy-engine/docs/reference/public-surface.md` | `5c06b4dafcb7397b4fd755f0642d98200111cdacae9d948c61f34790acdc3c57` | Architecture guardrails / public-surface owner |
| `policy-engine/docs/reference/schemas.md` | `20ccb87943f131b86387025a965a2b9e10f65498fb69c821af5c7597834c275b` | IR reflection catalog and ABI registry |
| `policy-engine/schemas/runtime_api_v1.openapi.json` | `701b5d6fe04afc283518f96ec5461db0fb3f7beb9fe33b82813a63b20e614ca0` | Runtime OpenAPI exporter |
| `policy-engine/schemas/snapshots/ir/_manifest.json` | `1f6e737b93879bb6c33fbc7bf4c5d847f66f1365720dc4702afdccaadb43d6e9` | IR ABI snapshot generator |
| `policy-engine/schemas/snapshots/ir/feedback_solve_result.schema.json` | `27dad4e3ca52c016d9203c5d70b27299bfbb38698fc6f64f4e2bc7377d2045d3` | IR ABI snapshot generator |
| `policy-engine/schemas/snapshots/ir/posterior_summary_profile.schema.json` | `fb26ce985c4b99092bd1a9d75a2f9b3940415eff83cbb9383fbb63a89b2dccf6` | IR ABI snapshot generator |
| `policy-engine/schemas/snapshots/ir/posterior_summary_profile_v2.schema.json` | `d538fc5a5b9003afd015eb59213a9fd72f5dcf7ab2ec830418e94124f13613d2` | IR ABI snapshot generator |

`feedback_solve_result` is an existing ABI companion, but the complete IR
registry check regenerates it along with newly registered Profile1/Profile2.
The packet explicitly records that Profile1's active registry entry lacked a
snapshot at base, so generating both posterior schema files is expected.

## Exact input closure and canonical commands

Use a read-only Git source snapshot of the *accepted, frozen integration SHA*
in a fresh ignored scratch directory. The source SHA for planning is E `717cea`
and its tree above; the execution pin must be replaced by the integrated SHA
after E source intake. Do not generate into the live G checkout.

The generator closure is broader than the nine outputs:

- ABI snapshots and IR docs: `tools/quality/diagnostics/gen_schema.py`,
  `generate_ir_reference_catalog.py`, `tools/lib/cache.py`,
  `src/polisyos/schemas/abi_models.py` (`IR_ABI_MODELS` and
  `select_abi_entries`), and the imported IR package. The reflection catalog
  (`src/polisyos/ir/schemas/catalog.py`) walks/imports the IR module tree and
  package facades; it consumes `src/polisyos/ir/api.py`,
  `src/polisyos/ir/__init__.py`, `src/polisyos/ir/analytics/__init__.py`, and
  the Profile2 definition in `src/polisyos/ir/analytics/posterior_summary.py`.
  Generate/check the complete `ir` selection derived from the exact frozen registry (the E planning snapshot has 101 members); do not use
  `--changed-only` as an abbreviated schema denominator.
- Public surface: `tools/devx/architecture/guardrails.py`,
  `architecture/public_surface/contract.toml`, all declared source-package
  facades under `src/polisyos/**/*.py`, and the generated-artifact manifest.
  Its sync command also considers `docs/reference/generated-artifacts.md`;
  that file is outside the nine-path allowlist and must remain byte-stable.
- Runtime OpenAPI: `tools/ops_runners/runtime/export_runtime_openapi.py`, the
  transitive runtime HTTP app/DTO source, and the exact source dependencies
  embedded in governed projection examples. The projected OpenAPI diff is three
  hunks changing the confidence-ledger-risk-spend projection/dependency hashes
  (`1489` to `1494` dependencies), not a new Profile2 HTTP endpoint. Its
  relevant source includes
  `architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json`.
  Recompute against the same frozen integration source that carries this
  ledger. A mismatch with the packet's `573` schema components / `1494`
  confidence dependencies is a source/dependency discrepancy to investigate,
  never a reason to hand-edit OpenAPI.
- Tool/runtime configuration: exact candidate `policy-engine/pyproject.toml`,
  `tools/lib/imports.py`, and Python package inputs. Record actual imported
  `polisyos` and `tools` module origins against the isolated source tree; the
  Git tree SHA is the complete file-set pin, not a substitute for checking
  runtime import provenance.

Documented canonical generators and equivalent direct-script invocations:

1. ABI snapshots plus both IR generated reference pages:
   `uv run --extra ml polisyos-tools diagnostics gen-schema --models ir`
   (`tools/quality/diagnostics/gen_schema.py`; `--models ir` selects the full
   IR registry and its generator also renders `schema-catalog.md` and
   `schemas.md`).
2. Public surface inventory and its reference page:
   `uv run python tools/devx/architecture/guardrails.py sync --skip-deep-import-baseline`.
   The flag prevents an unrelated deep-import baseline rewrite. This command
   also considers `docs/reference/generated-artifacts.md`; if that output
   changes, stop and review the unexpected companion rather than expanding the
   allowlist silently.
3. Runtime OpenAPI:
   `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/export_runtime_openapi.py --output schemas/runtime_api_v1.openapi.json`.
   The exporter has no `--check` flag. Recompute to a separate scratch output
   and byte-compare with the generated file for its deciding drift check. Its
   default CAS scratch directory is temporary and cleaned by the exporter.

For the eventual offline execution, use the existing G interpreter directly,
with `-S` and explicit `PYTHONPATH` entries for the isolated candidate's
`policy-engine/src`, candidate `policy-engine` root, and the existing venv's
`lib/python3.14/site-packages`. Set `PYTHONDONTWRITEBYTECODE=1` and
`PYTHONNOUSERSITE=1`. This avoids running the venv's editable-install `.pth`,
which points back at the live G checkout. The inspected G venv is Python
3.14.3/Pydantic 2.12.5/FastAPI 0.128.6/JAX 0.8.2/NumPy 2.3.5; E's recorded
author environment is Python 3.14.7 with the same Pydantic/FastAPI/JAX/NumPy
versions. `gen_schema.py` explicitly excludes `generated_at`, `python_version`,
and `pydantic_version` from manifest equality. Do not mutate the venv or run
`uv` in a way that syncs/installs packages. The existing `.pth` files observed
were `_editable_impl_policy_engine.pth` (live G paths) and `_virtualenv.pth`;
`python -S` skips both and the planned `PYTHONPATH` restores only candidate
source plus package bytes. If a required import fails under that profile,
record UNRUN/ERROR and the missing artifact; do not bootstrap dependencies in
this lane.

The generated-artifacts catalog names separate TypeScript client generators.
Those packages are not among the nine outputs here. Do not run a TS scanner or
client generator in this task; if the integrated OpenAPI diff requires client
output changes, hand that dependency to its canonical owner and require the
normal frozen-lockfile setup before any TS result is trusted.

## Deciding verification and negative controls

After the generator owner applies outputs in an isolated accepted-source copy:

- `python tools/quality/diagnostics/gen_schema.py --models ir --check --cache-dir <new-ignored-check-cache>` recomputes all selected IR schemas and both generated reference pages. The explicit cache path keeps verifier state out of the live checkout.
- `python tools/devx/architecture/guardrails.py check --skip-generated-checks` recomputes public inventory/reference drift and architecture contracts. Its output explicitly omits required generated-artifact freshness checks; do not report it as the full architecture freshness gate. The direct schema and OpenAPI checks cover the outputs in this lane.
- Re-run the runtime OpenAPI exporter to a new scratch JSON file and `cmp` it with `schemas/runtime_api_v1.openapi.json`. The exporter has no built-in `--check`.
- Assert the complete generated-file delta is a subset of exactly the nine paths above. A write to `docs/reference/generated-artifacts.md`, deep-import baseline, runtime client, other snapshot, or any source is a stop-and-review condition. Compare packet hashes as a diagnostic only; current integrated inputs are decisive.
- In a second disposable copy, alter a generated V2 schema field while retaining its `$id`/title; `gen_schema.py --models ir --check` must fail on the real schema content. Separately remove `PosteriorSummaryProfileV2` from the generated public inventory while leaving the source facade intact; `guardrails.py check --skip-generated-checks` must report public-surface drift. Preserve both complete outputs. These prove the generators recompute substance instead of accepting names/markers.

No broad workspace/CI run is part of this companion plan. Source consumers,
the E ratio law, and Finding closure remain separate G/E decisions.

## Known scoped typecheck failure

The E packet's exact 3932 one-module BasedPyright run used BasedPyright 1.39.0
and exited `1` with one `reportOptionalMemberAccess`: at
`src/polisyos/ir/analytics/posterior_summary.py:460`,
`envelopes[name].distribution_payload.model_dump(...)` is called while
`distribution_payload` may be `None`. The recorded base-resolved run has the
same diagnostic at the corresponding expression (base line 222), but this
module is part of the changed E source footprint. Under P41 this cannot be
called an inherited red with zero input overlap. Keep it as an unresolved
scoped typecheck failure; do not fold it into generated-companion acceptance
or claim a typecheck pass. G should report it to the canonical E code owner for
disposition or repair before any broader typecheck claim.

The accurate source-quality label remains `surface_missing` until generated
outputs are integrated and their checks pass. This plan neither accepts the
code nor closes a finding.
