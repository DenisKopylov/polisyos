# Import-policy primary-contract projection: blocked migration receipt

**Date:** 2026-08-26
**Base:** `main` at `b18937856`; adjudication input `a86d8983f`
**Branch:** `codex/import-policy-register-generated-matrix`
**Authority:** migration evidence and pair-by-pair proposals. The 21 pair readings below are not
ratified here and no import verdict is changed.

## Outcome first

The aggregate cannot honestly become a generated view yet. The read-only checker

```text
uv run python tools/quality/validation/check_import_policy_projection.py --check
```

completed at exit 1 and proved four independent blockers:

1. the executable matrix has 30 roots, while only 18 have root-level primary contracts;
2. the 18 contracts and the committed matrix disagree on 21 root pairs;
3. Runtime's primary contract uses `public_facades_only`, a predicate a finite root-pair allowlist
   cannot represent;
4. six primary contracts constrain DataForge access to `polisyos.data_forge.read_api`, which a
   root-pair projection would widen to all of DataForge.

Generating `architecture/imports/policy.toml` now would therefore either invent 12 contracts,
silently choose 21 architecture verdicts, invent a Runtime translation rule, or erase six narrow
submodule restrictions. A separate whole-file census also finds IR's external-module allowlist has
no source in the primary contracts. These losses violate the ratified stop condition. The committed
policy, package contracts, generated-artifact registry, and release guardrail were left untouched.
The checker is a read-only migration predicate; it has no writer and is not wired into a gate. The
generated-view capability remains `producer_missing` and the checker is
`implemented_but_not_orchestrated` until the owners ratify the missing inputs.

## Source derivation, not a replacement hand-list

The checker derives its sources by globbing `architecture/packages/*.toml`, parsing every file,
and selecting only documents whose `[package]` table declares `primary_contract = true`. It then
classifies a root contract only when `package.module` is exactly `polisyos.<root>`. Aggregate files
are excluded by shape (`package` is an array), and the one nested contract is excluded from the
root projection by module depth. No filename exclusion list exists in the checker.

Readiness also fails closed when the matrix-root census is empty, a selected root contract lacks a
string-list `boundaries.allowed_dependencies`, the Python source tree is absent, or a live source
cannot be parsed. Those are input-completeness failures, not evidence of an empty dependency set.

Two complete derivations agree:

- the checker parsed **19 primary files**, **18 root-level contracts**, and one nested contract;
- the adjudication input independently parsed the same TOML corpus and reconciled it against the
  aggregate boundary rows.

The 18 root contracts are `berl`, `calibration`, `common`, `core`, `data_forge`, `ddm`, `evidence`,
`fabric`, `foundry`, `ir`, `lex`, `method_requirement`, `obligation_graph`, `obligation_rules`,
`participation_requirement`, `runtime`, `scholar`, and `scientist`. The nineteenth primary file is
`architecture/packages/foundry-agent-sim-world.toml`, for the nested module
`polisyos.foundry.agent_sim.world`.

Only three of those 19 files—Fabric, IR, and Scientist—appear in the literal 21-file source corpus
of `architecture/gates/package_import.toml`. Derived discovery closes that source-list defect in
the checker without changing the existing gate corpus.

## Twelve roots with no primary contract

The checker and an independent set subtraction over the committed policy and contract modules
produce the same complete set:

1. `academic`
2. `batch_common`
3. `batch_snapshot`
4. `corpus`
5. `data_requirement`
6. `datasets`
7. `legal_requirement`
8. `pdc`
9. `policy_grammar`
10. `schemas`
11. `scholar_requirement`
12. `ukraine_data`

The checker reports each as `missing_contract_roots` and returns nonzero. It neither copies the
committed row nor emits an empty row, because either choice would silently allow or deny imports.

## Complete contract-to-matrix diff: 21 proposals

`policy-only` means the executable matrix permits the pair and the source root's primary contract
does not. `contract-only` means the primary contract permits it and the executable matrix does not.
Live counts come from a complete AST walk; the input report's independent anchored-import walk
agrees at **12 live pairs, 24 statements, 23 unique files**. Zero means the complete census found
none, not that a search sample missed it.

| Pair | Difference and sources | Live statements / files | Candidate reading for owner ruling |
| --- | --- | ---: | --- |
| `calibration -> core` | policy-only: `policy.toml:81`; `packages/calibration.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless Calibration supplies a concrete dependency case. |
| `evidence -> ir` | policy-only: `policy.toml:87`; `packages/evidence.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless Evidence establishes the direction. |
| `fabric -> data_requirement` | policy-only: `policy.toml:71`; `packages/fabric.toml` omits it | 1 / 1 | Preserve neither document by inference: Data Requirement lacks a primary contract. Appoint its owner, then place or relocate the adapter before changing the pair. |
| `foundry -> calibration` | policy-only: `policy.toml:72-80`; `packages/foundry.toml` omits it; layered siblings also oppose it | 1 / 1 | Prefer the contract/layer reading: inject or relocate calibration policy, then remove the broad matrix allowance. |
| `foundry -> fabric` | contract-only: `packages/foundry.toml` and `packages/boundaries.toml` permit it; `policy.toml:72-80` and `imports/contracts.toml` forbid it | 2 / 2 | Candidate-ratify only the narrow evidence-path dependency, with a supported Fabric surface. Strongest counter-argument: this revises deliberate sibling-layer semantics. |
| `foundry -> method_requirement` | policy-only: `policy.toml:72-80`; `packages/foundry.toml` omits it | 2 / 2 | Preserve the direction and add the explicit primary-contract dependency if Method Requirement confirms these are lower-layer requirement DTOs; otherwise relocate. |
| `ir -> schemas` | policy-only: `policy.toml:67`; `packages/ir.toml` omits it | 1 / 1 | Preserve provisionally only if the missing Schemas contract appoints it as a neutral ABI below IR; do not encode that appointment here. |
| `lex -> batch_common` | policy-only: `policy.toml:114`; `packages/lex.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless Lex supplies a current use. |
| `lex -> legal_requirement` | policy-only: `policy.toml:114`; `packages/lex.toml` omits it | 1 / 1 | Preserve provisionally only if the missing Legal Requirement contract confirms the lower-layer input relationship; otherwise relocate. |
| `method_requirement -> ir` | policy-only: `policy.toml:85`; `packages/method_requirement.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless the owner establishes need. |
| `obligation_graph -> ir` | policy-only: `policy.toml:110`; `packages/obligation_graph.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless the owner establishes need. |
| `obligation_rules -> ir` | policy-only: `policy.toml:68`; `packages/obligation_rules.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless the owner establishes need. |
| `obligation_rules -> runtime` | policy-only: `policy.toml:68`; the primary contract explicitly forbids Runtime | 0 / 0 | Remove the matrix allowance; retaining it requires an explicit contrary ruling. |
| `participation_requirement -> ir` | policy-only: `policy.toml:86`; `packages/participation_requirement.toml` omits it | 0 / 0 | Remove the unused matrix allowance unless the owner establishes need. |
| `scholar -> data_forge` | contract-only as narrow `polisyos.data_forge.read_api`; `policy.toml:113` denies the root | 0 / 0 | Preserve the matrix denial: adding a root pair would widen a narrow contract. Retire the unused boundary allowance or define a separately enforced narrow predicate. |
| `scholar -> scholar_requirement` | policy-only: `policy.toml:113`; `packages/scholar.toml` omits it | 5 / 5 | Preserve provisionally only if the missing Scholar Requirement contract confirms the lower requirement relationship; otherwise relocate the five consumers. |
| `scientist -> calibration` | policy-only: `policy.toml:88-106`; `packages/scientist.toml` omits it; layered siblings oppose it | 1 / 1 | Prefer the contract/layer reading: inject or relocate the calibration computation, then remove the broad allowance. |
| `scientist -> evidence` | policy-only: `policy.toml:88-106`; `packages/scientist.toml` omits it | 3 / 3 | Preserve the direction and add the primary-contract dependency if Evidence confirms the shared lower artifact surface. |
| `scientist -> method_requirement` | policy-only: `policy.toml:88-106`; `packages/scientist.toml` omits it | 1 / 1 | Preserve the direction and add the explicit lower requirement dependency after owner confirmation. |
| `scientist -> participation_requirement` | policy-only: `policy.toml:88-106`; `packages/scientist.toml` omits it | 2 / 2 | Preserve the direction and add the explicit lower requirement dependency after owner confirmation. |
| `scientist -> runtime` | policy-only: `policy.toml:102`; both boundary contracts explicitly forbid it; layered order also forbids it | 4 / 4 | Prefer the two contract/layer readings: relocate the calls or establish a narrow surfaced bridge, then remove root-wide Runtime access. |

These are proposals, not changes. Every pair remains exactly as `policy.toml` currently decides it.

## Two further projection losses

First, six primary contracts allow only `polisyos.data_forge.read_api`: IR, Fabric, Foundry, Lex,
Scholar, and Scientist. A root-pair matrix can project only `-> data_forge`, losing the submodule
restriction. The checker reports all six under `granularity_collapses`; it does not hide the
widening behind normalization, and each collapse blocks readiness even when the projected root pair
already agrees with the matrix.

Second, `policy.toml` also carries IR's seven-module external allowlist. Primary package boundary
contracts encode internal FQNs, not external-module permissions. A whole-file generator sourced
only from those contracts would silently drop the external rule. The current checker therefore
checks only the root matrix and refuses to claim that the whole file is generated.

## Gate disagreement and corrected prior findings

The hand-over asserted that the package-import gate was green on merged `main`. A fresh exact replay
did not reproduce it:

```text
start  12:01 up 2 days, 2:14
end    12:06 up 2 days, 2:19
exit   1
findings 143
user 162.91 + sys 11.71 = 174.62 CPU-seconds
```

The gate reports the 23 expired exceptions, forbidden-boundary growth, dynamic imports, and other
structure findings. It also does not compare `policy.toml` allowsets to primary contract
allowsets and skips `public_facades_only`; a future exit 0 would still not prove matrix/contract
agreement. Findings 3 and 5 in the adjudication report now state those separate predicates and the
fresh disagreement.

## Pattern pass

- `P06`/`P27`: derived discovery avoids a second hand-maintained source list.
- `P35`: the projection denominators—19/18 contracts, 12 missing roots, 21 differing pairs, and the
  12-pair/24-statement/23-file live subset—are independently enumerated twice. Unreadable or absent
  Python sources are explicit `ambiguous_import_sources` blockers rather than zero.
- `P37`/`P38`: the checker measures pair-set equality itself and separately names the Runtime and
  submodule semantics the matrix cannot express.
- `P41`: the package-import gate's fresh red is recorded as its own predicate; it is not exported
  as a failure of this read-only projection checker.

`guardrails sync` was not run. No exception was added, removed, or renewed.
