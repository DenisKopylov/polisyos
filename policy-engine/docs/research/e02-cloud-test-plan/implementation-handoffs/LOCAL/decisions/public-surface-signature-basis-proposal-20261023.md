# E02-PS-SIGNATURE-BASIS-01
## Proposal for independent G decision: public API signature evidence

Status: proposal for G only. This packet is not an accepted decision, code acceptance, or closure. Scope is only the mismatch between the public-surface README promise and the generated inventory. It does not decide the export-dependency-slice mechanism, namespace routing, or runtime origin.

### Decision requested

Choose what “signature” means in the public-surface inventory:

A. a source-declared AST observation, explicitly distinguished from runtime behavior;
B. runtime introspection of one identified installed artifact; or
C. no generated signature field, with docs limited to emitted fields and changes left to package-owner review.

Team-architecture owns the inventory policy; package owners own API compatibility review. G adjudicates this contract semantics.

### Evidence and denominator

R71-F2 is a packet-local cross-reference to “Signature inventory mismatch and narrow G choice” in the read-only audit; it is not a canonical finding ID. R71 report: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/resume-public-export-independent-20261022-r1/public-export-scanner-systemic-design-audit-r71/report.md` @ `e0f874786e0db952a82662452dffa514754250368c86efcd6041a8a0a047ac64`.

The README @ `0d395c9f23e51a0890992eafec2269d14f7ff3e14849138d8387a2fe533aa298`, lines 3-5, says generated JSON captures exported names and signatures. Lines 22-23 require package-owner review for signature changes and a SemVer decision when breaking. Contract policy @ `cce2e7cd4d96b4595ae5bf0721002776265d70f878d4fbfcd51570f9d89f10c9` names team-architecture as owner.

A complete walk parsed every `[[package]]` row and every `supported_entrypoints` item in the contract, then parsed the generated JSON and recursively inspected all object keys. Deciding output:

```text
contract package rows: 20
contract supported entrypoints: 84
inventory package rows: 20
inventory entrypoints: 84
package rows with null export_count: 20 / 20
entrypoint rows with null export_count: 84 / 84
recursive inventory keys named "signature": 0
```

Inventory: `policy-engine/architecture/public_surface/inventory.json` @ `483f74bc8c7b61b4a3d48f8dd46c55de0e747ec825f5bae4ed3b01c28288039f`. Thus no signature observation exists for any of the 84 declared entrypoints or their exports; null export totals are not signature evidence. This is a docs/schema mismatch separate from R71's export completeness and runtime-origin findings.

There is a reusable but separate source-AST mechanism in `policy-engine/tools/quality/validation/decomposition_preflight.py` @ `25cd590f71ea1f4c4fbe3472775f8981f592c9918d734d7607442b477dcfef3c`: `collect_public_surface_snapshot`, static alias resolution, and `_public_surface_definition_record` emit a signature for source-defined functions. Current `_signature` unparses arguments only; it omits return annotations and decorators. Class records have no effective constructor signature. This is a structure-remediation snapshot, not the 20-package/84-entrypoint policy inventory. Its test @ `d23dddb1f4da7c8ce471dde6f2d33cf2f7377fef60992608c6e27c7235778989` proves a parameter change is retained by that snapshot normalizer, not that the policy inventory or installed call behavior is covered. Baseline @ `4d8b67ee939c769b8cd52b9cdae49597d040b9680304e63356b1c449b0eef589`.

R71's installed-composition check resolves declared `__all__` names with `getattr`, but does not compare signatures. It is evidence only for the selected test environment.

### Alternatives and consequences

| Option | Status, authority, time | Migration and compatibility | Owner and cost |
|---|---|---|---|
| **A. Source-declared AST (recommended)** | Label `source_declared`; observation of source syntax, not runtime authority. Bind it to the frozen source tree. Unresolved or dynamic binding is `not_established`. | Version inventory to v2 and keep a v1 reader during migration. Reuse AST and alias-resolution logic, joining only the proven exports of the 84 declared entrypoints; do not copy the broad baseline wholesale. Canonicalize parameter kinds, defaults, annotations, and return annotation. Keep decorator effects and class-generated constructors outside this field and explicitly unestablished. No runtime API/import behavior change. | Team-architecture sets schema; tooling owner implements; package owners review. Moderate bounded cost: projection join, schema, regeneration, and drift/removal test. |
| **B. Installed `inspect.signature`** | Label `runtime_introspected`; bind to a named wheel/build, Python and dependency profile. No authority beyond that observation and no later/production currentness claim. Inspection may be unavailable; it must not default. | Requires artifact/profile identity in v2 and an exact-wheel consumer. Imports may execute side effects and optional dependency paths. Wrappers, `__signature__`, metaclasses, and environment can change results. Introspection metadata does not prove accepted call behavior. | Team-architecture plus build/release/toolchain and package owners. High cost: isolated builds, profile binding, import safety, receipts, upkeep. |
| **C. Narrow documentation** | Say the inventory records names, counts, and status only. It carries no signature evidence or signature time basis; package-owner review remains the control. | No schema/runtime migration. Update README and release guidance so inventory-review status cannot imply automated signature comparison. This retracts the current generated-signature claim but preserves owner review. | Team-architecture and release-doc owner. Low code cost; weaker generated drift coverage and continuing manual review. |

### Recommendation

Choose **A**, narrowly: “signature” means a source-declared function signature observation, never an effective runtime signature. Reuse the AST and static alias-resolution work but join only proven exports in the declared 84-entrypoint denominator. Include parameter kinds, defaults, annotations, and return annotation. Do not claim a decorated wrapper, class constructor, or dynamic callable signature without a separate evidence basis. Package-owner review remains required for all behavior changes; a source observation does not itself make a breaking change admissible.

If G rejects that distinction, choose C instead of silently calling AST data runtime behavior. Choose B only if the product wants environment-bound introspection and funds its exact-artifact/profile chain.

### Prototype, falsifier, and pending default

Prototype one fixture package containing a direct function, re-export alias, signature-changing decorator, and callable class with a generated constructor. Compare source observation with an identified installed-wheel observation and report their bases separately.

For A, change a parameter or return annotation while retaining `__all__`: the source drift check must fail. Remove the implementation but retain `__all__`: the installed-name consumer must fail. The decorator and class must expose source/runtime divergence without relabeling. For B, test two identified profiles where runtime introspection differs or is unavailable. For C, verify docs no longer claim JSON includes signatures and retain the owner/SemVer review rule.

Until G decides, keep schema v1 unchanged and record **signature inventory: absent / not established**. Add no guessed fields; do not mark signature drift as machine-reviewed. Preserve package-owner/SemVer review. R72's declaration-slice implementation and exact installed name join proceed independently; this question does not block export names, `__all__`/attribute resolution, or exact-artifact name checks.

This packet does not alter `pkgutil.extend_path` or namespace compatibility. Keep the ordinary namespace route as-is; retain R71's bounded `runtime_origin=not_established` where there is no exact installed-origin witness. No new G decision is requested for origin.

### Choice for G

Select A, B, or C and record migration/release-review implications. The author recommends A. Formal decision, acceptance, and closure remain with G.
