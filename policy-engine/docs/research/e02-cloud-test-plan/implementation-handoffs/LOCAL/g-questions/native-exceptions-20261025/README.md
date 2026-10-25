# G question packet R2: reflection on supported public Fabric APIs

## Decision requested

For the **11 supported public-stable Fabric annotation sites whose reflection contract remains unresolved**, does compatibility promise successful typing.get_type_hints resolution, or are annotations required for static typing unless runtime reflection is separately promised?

**Recommendation:** preserve the current reflection behavior for those 11 signatures with exact TC001/TC003 exceptions and supported-facade tests. This is a scoped contract question, not a package-wide reflection rule. ConnectorMetadataSpec is already settled; RuntimeLineageRef and RuntimeQuantityValue are internal implementation choices.

## Scope and evidence

The complete Ruff result contains **14 Fabric diagnostics across five modules**: TC001=11 and TC003=3. Their corrected partition is **11 public sites with unresolved reflection contract + 1 already-bound public + 2 internal**. The full source denominator is 502 Python files across Fabric and IR. R2 preserves all 14 diagnostic rows and their individual outcomes.

An independent reviewer ran the exact 14 source bindings in isolated copies: 14/14 get_type_hints positives and 14/14 exact-global-removal NameError controls. The complete command is pinned in inputs.json as invocation.json; complete stdout, stderr, receipt and per-binding results are also referenced there. This establishes current behavior, not a public guarantee.

RuntimeQuantityValue was misclassified as a public choice in R1. The owner surface contract lists supported Fabric entrypoints and does not list polisyos.fabric.evidence; the stable root facade does not export from_runtime_quantity. The README describes the module as a legacy compatibility path, but this does not designate that helper as a supported public API. Its annotation disposition is therefore local implementation work. The two internal rows remain in the 14-item diagnostic denominator.

## Choices

- **A — preserve (recommended):** retain runtime bindings for the 11 named public signatures, use exact rationale-bearing TC001/TC003 suppressions, and verify each through a supported entrypoint. Do not add a broad owner ignore.
- **B — static-only:** permit those 11 imports to move under TYPE_CHECKING, preserving ordinary calls and static checking while making no get_type_hints promise for them. G should say whether that is a public-stable API removal under the existing policy before implementation.

Keep ConnectorMetadataSpec unchanged; its source comment and two existing tests already bind its runtime reflection. Decide the private RuntimeLineageRef and internal RuntimeQuantityValue rows as executor work. No waiver platform, date extension, or global source freeze is requested.

## Pattern pass and acceptance

Relevant patterns are P35/P36 (complete denominator and supported-surface boundary) and P38. The property is a public compatibility promise for supported APIs; the observed implementation currently resolves all 14 module annotations. RuntimeQuantityValue is a divergent case: it resolves today, but belongs to an unsupported evidence helper path, so runtime behavior alone cannot establish a public promise. The target pattern is an explicit supported-entrypoint contract with occurrence-level status. Acceptance is a narrow G answer for the 11 rows and subsequent supported-facade positive/removal controls. This packet does not claim capability closure or code acceptance.

The 16 RUF100 results came from the narrow N818,RUF100 profile and concern suppressed codes outside that rule set. The full active-config scan and complete-scope N818-only scan are green. These are not active Ruff debt and do not reopen G's N818 exception-identity decision.

## Source and decision references

- [Public-surface owner contract at source frame 49dff918](https://github.com/DenisKopylov/polisyos/blob/49dff9183c20be3877d47953e0142417cb854cd0/policy-engine/architecture/public_surface/contract.toml)
- [Fabric public facade at source frame 49dff918](https://github.com/DenisKopylov/polisyos/blob/49dff9183c20be3877d47953e0142417cb854cd0/policy-engine/src/polisyos/fabric/__init__.py)
- [Fabric README at source frame 49dff918](https://github.com/DenisKopylov/polisyos/blob/49dff9183c20be3877d47953e0142417cb854cd0/policy-engine/src/polisyos/fabric/README.md)
- [Full 14-row ledger, source/config pins, commands and probe hashes](inputs.json)

code_acceptance=false, closure_ids=[], and global_source_input_backend_freeze=false. G retains formal decision authority.
