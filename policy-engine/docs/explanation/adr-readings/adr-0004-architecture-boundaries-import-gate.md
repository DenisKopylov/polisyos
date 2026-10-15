# English reader translation of ADR-0004: Architecture boundaries import gate

Document type: English reader translation (informational derivative)  
Source pin: `af387828fbf27dce6dec8665286180df0dd10d1c`  
Source of truth: `docs/adr/0004-architecture-boundaries-import-gate.md`

This page translates the decision text in the [source ADR](../../adr/0004-architecture-boundaries-import-gate.md), whose SHA-256 is
`2499ef60640c97deb0ab43f0f5c9c6c67694c699b8829c693e3a98cdad4fa626`.
The generated ADR index reports the source status as `unknown` at the source pin.
This derivative does not ratify or revise the decision and does not establish
that the decision was implemented.

- **Date:** 2026-02-03
- **Decision:** Establish platform layers as ABI boundaries and introduce a
  mandatory AST import check against a dependency matrix. The single source of
  truth is `architecture/imports/policy.toml` +
  `architecture/imports/exceptions.toml` +
  `tools/quality/lint/lint_imports.py`.
- **Context:** Before this decision, import rules were partly documented and
  partly encoded, which caused divergence and hidden cycles. A single,
  verifiable layer contract is required.

## 1. Layers and responsibilities (architecture ABI)

- **ir (Contract plane):** Pydantic models, enums, contract registries / types,
  formats, and contract migrations only. Imports are limited to
  `polisyos.ir.*` and external dependencies: stdlib + `pydantic` +
  `typing_extensions`.
- **core (Infrastructure kernel):** CAS, canonical JSON, refs,
  trace/observability, and stable integration points. Imports:
  `polisyos.core.*`, `polisyos.ir.*`, and optionally `polisyos.common.*`.
- **fabric (Data/world plane):** artifacts, fact log, materialization, and
  queries. Imports: `polisyos.fabric.*`, `polisyos.core.*`,
  `polisyos.ir.*`, and `polisyos.common.*`.
- **foundry (Compute plane):** compute over artifacts. Imports:
  `polisyos.foundry.*`, `polisyos.core.*`, `polisyos.ir.*`, and
  `polisyos.common.*`.
- **scientist (Control plane):** orchestration / workflow / governance. It may
  import all lower layers.
- **runtime:** the execution service layer. Imports: `polisyos.runtime.*`,
  `polisyos.core.*`, `polisyos.ir.*`, and `polisyos.common.*`.
- **scholar / lex (future):** service domains that may import ir/core/fabric/
  common and are used by scientist.

## 2. Dependency matrix (in code)

The matrix is the single source of truth and is stored in
`architecture/imports/policy.toml`.

## 3. Legacy / `_legacy` policy

- `polisyos.ir.legacy.*`: deprecated / compatibility code. Only
  `polisyos.ir.*` and external allowlists (stdlib + `pydantic` +
  `typing_extensions`) are allowed. Everything else requires an exception
  with an expiry.
- `polisyos.scientist._legacy.*`: allowed within scientist, but **must not be
  imported from below** (from any module outside `polisyos.scientist.*`).

## 4. The "contracts only" rule

Cross-module interaction is allowed:

- through IR contracts (`polisyos.ir.*`), or
- through CAS artifacts / refs (strings / refs) indexed by Fabric.

## 5. Automated import gate

The AST checker `tools/quality/lint/lint_imports.py` checks imports against
the matrix, accounts for exceptions, and fails on new violations or expired
exceptions.

## Amendment A (2026-02-10): P1 Import Policy v2

- `architecture/imports/policy.toml` was moved to `version = "2"`.
- The scientist import matrix was made explicit (without wildcards); `packs`
  remained temporarily wildcarded through P2.
- `architecture/imports/exceptions.toml` and
  `architecture/imports/exceptions.md` were moved to managed mode with active
  P1 debt permits (owner + expiry).
- `tools/quality/lint/lint_imports.py` was tightened:
  - A complete `internal.allow.*` matrix is required for every
    `roots.known`.
  - Duplicate `exception.id` values are treated as a configuration error.
- Normative specification: `p1_import_policy_v2_spec.md`.

## Related Decisions

- Extended by: ADR-0115 (layered architecture enforcement), ADR-0127
  (repository hygiene gates).
