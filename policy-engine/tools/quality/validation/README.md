# tools/quality/validation

Validation ratchets for docs, benchmark contours, CI policies, and quality baselines.

Use the unified entry point:

```bash
polisyos-tools validation --help
```

## Dynamic import inventory

`architecture/imports/dynamic.toml` records source-owned dynamic import patterns. The
`decomposition_preflight.py` gate derives its expected rows from `collect_dynamic_imports`
and rejects missing, stale, or malformed inventory. The collector analyzes syntax and
source bindings without importing or executing the inventoried modules.

For an immutable source-owned `MappingProxyType` with fully known builtin literal keys,
exact .get(...) and subscription lookups follow Python's key equality and duplicate-key
behavior: only the effective value selected by an exact key contributes an importer target. The bounded lookup keys are builtin hashable literals and recursive tuples of those literals.
Mapping membership is a separate source-analysis path and is not broadened by this exact-lookup
change: existing string-membership and tuple-route controls remain unchanged, while the probed
exact-integer-membership guard followed by lookup remains fail-closed because that path has not
established the selected value. Dynamic or unresolved keys, unknown mapping unpack, unhashable
literals, and user-defined key behavior remain ambiguous and do not become an empty/default allowlist. A finite target list is derived
from the selected source-bound importer values; it does not issue or renew owner review
metadata in `dynamic.toml`.

## Docs lifecycle removed-reference scan

`check_docs_lifecycle.py` keeps the lifecycle checker and CLI surface. Its removed-stub reference scan is implemented by `docs_lifecycle_reference_scan.py`; the facade supplies the current repository enumerator, reader, selector, finding type, and path formatter through a typed dependency value. This preserves injected test enumerators without mutating scanner module globals. The scan receipt remains scoped to this one check. Excluded, opaque, or malformed inputs continue to produce partial or ambiguous coverage rather than a complete lifecycle-gate claim.

## Directory-health dashboard composition

`directory_health.py` remains the CLI and report facade. Its dashboard metrics and inventory
aggregation live in `directory_health_dashboard.py`; calls receive the active facade dependencies,
so report generation continues to use the same tracked-file, filesystem, contract, and finding
inputs as the CLI and imported API.

## Repository-structure inventory

`repository_structure_phase0.py` retains the CLI, gate composition, and compatibility facade. `repository_structure_phase0_inventory.py` owns the inventory scan; the facade passes its current helpers and policy constants as typed dependencies so existing callers and monkeypatch seams continue to work.

### Docs review, ADR compilation and production-quality inventory

`check_docs_review.py` keeps the review CLI and current facade configuration;
`docs_review_git.py` owns Git window selection, while `docs_review_artifacts.py`
owns review artifacts and retained command logs. Dependencies are supplied from
the facade for each call so current output roots and command callbacks remain active.

`generate_adr_index.py` keeps the CLI and current path configuration.
`adr_index_compiler.py` owns ADR parsing, classification and index compilation;
the facade supplies its current paths to the compiler. Generated output ownership
and check behavior remain unchanged.

`production_quality_evidence_inventory.py` keeps the inventory entry points.
Its `_bindings`, `_contracts` and `_reports` siblings own source binding resolution,
inventory contracts and producer report specifications. CI and Wave40 consume this
static inventory in their existing roles; the inventory does not establish that
those producers ran for a current transaction or authorize publication.

### Honest diagnostics and trust posture

`build_honest_diagnostics_coverage.py` owns the coverage CLI, rendering and current
configuration. `honest_diagnostics_coverage_metrics.py` owns metric definitions,
parsing and calculations; the facade supplies its current contract bindings and
keeps the existing one-argument validation callback.

`check_trust_claim_posture.py` remains the compiler facade. Its contracts, tokenizer,
source bindings, accessibility, semantics and artifact-lifecycle siblings own the
corresponding calculation families. The facade supplies current callbacks for each
call, including the probe-repository adapter used by source read-receipt checks.
The existing source owner, generated artifact contract and output paths remain in
place. These source extractions require behavioral and removal checks before any
native-gate completion claim.
`directory_health.py` remains the CLI and report facade, while `directory_health_dashboard.py` and `directory_health_inventory.py` own dashboard composition and bounded-retention path inventory. The inventory streams the existing tracked, ignored, raw, and filesystem scopes; consumers apply selectors during traversal and preserve required output rows and ordering. A Git iterator is complete evidence only after exhaustion, and the report-only Git fallback is not a completeness authority; native behavior and resource acceptance require focused tests and actual CLI-output readback.

`check_layer3_gy_promotion_contract.py` remains the CLI and compatibility facade. It passes the current confidence-ledger session, output path, and registered epoch-reissue callbacks into private owners so existing imports and monkeypatch seams remain active. `layer3_gy_n9_contract.py` builds the live contract through `polisyos.runtime.quality.promotion_sequence`; `layer3_gy_n9_comparison_custody.py` owns frozen comparison identity and authorized epoch transitions; `layer3_gy_n9_promotion_mutations.py` owns behavioral and source-flip probes; and `layer3_gy_n9_contract_inputs.py` owns typed synthetic inputs. The artifact path, schema, CLI, promotion authority, and registered tests remain at their existing surfaces.

`check_layer3_gy_openalex_artifacts.py` remains the CLI and validation facade. `openalex_span_evidence.py` owns recorded-provider population, extractor-accuracy recomputation, and candidate SKG proof production; the facade supplies its active source paths, readers, provider callback, digest, strangle check, and storage factories per call. The existing literature, SKG, generated-artifact lifecycle, history-integrity, and adjudicator-authority owners remain authoritative. The extraction does not promote accuracy or change generated-artifact identity; its bounded recorded-response population must not be described as the global/live OpenAlex population.

`architecture/packages/*.toml` remains the primary package-row source; this nine-file R3 slice aligns twelve routine fields with the current public-surface aggregate. The `polisyos.runtime` / `polisyos.runtime.quality` G route choice remains unresolved, and the package-mirror writer plus its runtime/consumer path are outside this source slice and unverified.
