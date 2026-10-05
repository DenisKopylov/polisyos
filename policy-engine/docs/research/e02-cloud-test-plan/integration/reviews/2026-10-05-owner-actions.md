# G: owner actions and remaining acceptance

This is an integration queue, not a finding ledger. An owner's `closure_ids`
field identifies related findings; it does not override an explicit partial
disposition or authorize G to close them. Accepted code, evidence adequacy,
and authority/capability closure are separate decisions. Checkpoint-06 adds six
bounded code slices to the earlier accepted heads and preserves their original
history. No finding closure follows from those merges.

## Deciding local HOLD

| Canonical writer | Immutable input | Property and deciding output | Required owner action |
| --- | --- | --- | --- |
| B: executor | `3e95056bca6d0c15ab7778573172491628f48596` | Callback capacity and shutdown dependency cycles remain real deadlocks; [callback](../checks/b-executor-callback.json) and [shutdown](../checks/b-executor-shutdown.txt). | Reconcile the capacity/lifecycle invariant or declare its supported boundary with a falsifier. Passing authored tests are not the missing invariant. |
| B: connection pool | `d9d61af6359033a08835cf5cc3fecb41c8e6967f` | A cancellation-suppressing connect/health returns a handle after the total acquire deadline; publication and permit remain observable. [G deadline witness](../checks/b-pool-deadline.json). | Refuse publication after expiry and own cleanup of a returned handle. Hard physical cancellation needs a protocol/cleanup owner; it cannot be inferred from `wait_for`. |
| C: streaming | `789e9e906cc52ff544fb05d4faa5db13359fee84` | A checkpoint retains two rows at cap 3; restart at cap 1 with an exhausted source restores and persists both rows while returning CLOSED. [G restore witness](../checks/c-streaming-restore.json). | Admit restored rows/JSON bytes before poll/flush, or reject an incompatible saved/current processing contract. Existing retry raises the cap; it does not exercise this case. |
| D: transfer | `e608502d9f885d87ce580175cc95f8f17689f6e0` | A public dimension reader sees new dimensions with old generation keys during publication. [G transfer witness](../checks/d-transfer-native.json). | Bind every public reader to the same generation invariant. Later source commits require delta evidence; this receipt does not decide those commits. |
| D: RL/search | `86584ad12436b10153efcf955e3eb7da3bdbc26d`; later source `4030275fd5bfb9c2a94c78b0f56e8d8aec97a83a` | JSON bool/float version admits as version 1. [G admission witness](../checks/d-rl-admission.json). The later decoder repairs `metadata.base_state`; its package also carries sibling source changes. | Bind an exact combined candidate/tree and all sibling dependencies, with the typed version discriminator. The separate GP witness is not evidence for the full source package. |
| E: covariance/Monte Carlo | `f07058a3eb782463eedce65a6d0d54c332a46efe` | Finite PSD covariance `1e40` passes validation, then float32 narrowing produces 1,024 nonfinite evaluator draws on random, Sobol and Halton. [G range witness](../checks/e-cal-uq-range.json). | Preserve the admitted law or refuse unsupported range before evaluation. Ordinary full-rank and singular covariance controls pass; they do not establish the unrestricted range claim. |
| B: durable budget ledger | `510a6076e91f6c5ea540845d77b8d83d0b4a3cb5` | Cold public `record_spend` creates a no-limit ledger; later configured middleware accepts what a freshly configured control blocks. [G cold mutation witness](../checks/b-dur-cold-mutation.json). | Bind mutation to admitted ledger configuration before persistence. This is the same configuration/admission class deeper at the public writer; in-repo production reachability was not established. |

These are property failures, not missing production datasets. Both successful
probe processes and expected-red controls are interpreted from their actual
observations. A process exit alone is never the deciding property.

## Receipt and authority holds

B CAS has post-candidate runtime/test changes not bound by its current receipt.
The exact newer diff and its dependencies need review. The newly observed B EXE
source delta and the aggregate E assessment branch similarly require their own
current source binding; an older review applies only to unchanged content.

D's separate GP receipt supports its numerical property on its pinned source.
It does not admit the entire search lineage, whose source also changes RL,
coordinates, stopping and neural/autotune consumers. D funnel's callback and
`promotion_write_allowed` flag do not supply a typed independently verified
owner grant. Its bounded candidate work remains separate from authority
closure.

E DDM's conditional root-export test does not preserve the prior public API
oracle. E FRC supports a predictive producer and persisted method/rule/count
bindings, while S10 credible-evaluation content/verifier provenance remains
`verification_missing`: byte-valid role/report/identity fields alone can pass
the callable seam. The default live route is not established. FRC-01's two
recorded failures remain open; no P41 exclusion or weakened gate is allowed.

A's N5 persisted conditional route is substantively bound for the exercised
list-candidate shape. Independent reviews name two residuals for A to decide:
the grammar fallback has `atom` but N8 only derives expected IDs from
`intervention_atoms`, and the adjacent CAS-less EvalSafety path can label a
shape-valid arbitrary digest `recomputed`. Neither residual is a full N5/N8
custody closure. ASGI POST/GET and the default production profile remain
`verification_missing`.

C BERL validates embedded records but its reference-only reliability path does
not resolve/content-bind the referenced bundle. C Ukraine's installed console
route is supported, while the checkout-file proxy and contradictory
`PartAGateManifest(passed=true, status="failed")` remain authority holds. C
Scholar improves snapshot metadata but its historical v1 bridge still compares
against a mutable current URL-cache record; final knowledge/event consumption
and DNS rebinding protection are unestablished. C embeddings verifies selected
generation/store readback, not model/query compatibility, independent source
membership, the legacy fallback, or the producer stage-manifest lifecycle.

## Dependency and consumer queue

A custody contains the source dependency and the final test blob that also
appears on its separate N5 readback topic. The leaf readback topic does not
contain that source dependency. C BERL declares a Ukraine ops dependency absent
from its candidate ancestry; both touch `pyproject.toml`, and BERL also changes
`uv.lock`. These are dependency interlocks, not a demonstrated merge conflict.
G must reconcile the combined identity and replay affected consumers; an
actual conflict is returned to the canonical writer, never repaired by G.

| Declared edge | Current evidence and remaining check |
| --- | --- |
| CYC-01 → FRC-01 | N5/runtime identity and forecast history-purpose admission are separate. The two FRC-01 failures require the A shared consumer; predictive producer acceptance cannot close them. |
| EMP-01 → FRC-02 | A's real DuckDB scope-before-limit/unit tests are useful B16 witnesses. They stop at the value owner gateway; no calibration producer/S10 credible-evaluation authority bridge is established. |
| CYC-02 → RES-03 | Fresh-process N5 readback is not the required ordinary earlier-success/later-failure result lifecycle. Native B EXE cache/checkpoint evidence is also a separate property. |
| NET-01 → ING-02 | B's acquire-deadline witness and C's lower-cap restart witness both remain held. Recheck the integrated pool/streaming consumer when the owners settle those contracts. |

The Core-to-IR adapter is a bounded ready slice, still not admitted by
checkpoint-06. After its contract changes,
recheck composition and real metric-validation/IC callers, including callers
that still supply a Core store directly. PCL/BKT/FRC share an affected wave
after bias/FRC supplier decisions. C plugin discovery/training share their
legacy registry and require a combined consumer check; FRY's mechanism registry
and F's causal-method facade are separate ABIs. C OBS's per-file snapshot fix
does not establish a source cohort or stale-panel release gate.

## Verification limits

G has provisioned the frozen Python dependency profile and supported host
Node 22/pnpm dependencies; [environment receipt](../checks/g-environment.json)
records setup, not product PASS. Numerical/data work is serialized locally;
B/D/E/F cloud runs are not capped by that slot. Available generic synthetic
witnesses do not require copying production data. Admitted-law, historical
data, calibration and other criterion-dependent inputs remain unestablished
where their owner has not supplied them. Raw source archives are unavailable.

The expensive backend/CI/replay wave remains UNRUN until a source freeze and
all reviews. Broad reds have `not_established` provenance unless the exact
command is replayed at the slice base and the complete input intersection is
zero. No main publication is authorized.

Pattern pass: P29/P32/P37/P38 require actual content and predicate evidence;
P33 keeps the property wider than its witness; P40 buckets the described
deeper escapes rather than starting serial instance repairs; P41 preserves
unknown red provenance. Missing consumer, bridge, surface and verification
labels are retained above instead of promoting diagnostic evidence.

[Recovered workspace drafts](2026-10-05-recovered-work.md) give exact published
archival refs and minimal adaptation/negative-test instructions for the
canonical owners. Retirement of their checkout directories does not admit
their code or close their findings.
