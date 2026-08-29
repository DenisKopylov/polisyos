---
task_id: INT-R3
stage: 2
artifact_role: independent_audit
audit_target: 819a83a88315a90320fdd4b25fcb328b434c77de
audit_base: dc7bdf79a1eff91349351a2f11dc498fe1ad7b4f
branch: research/int-r3-independent-audit
verdict: GO_WITH_REVISIONS
status: complete
finding_total: 23
severity:
  blocking: 0
  material: 13
  minor: 5
  commendation: 5
---

# INT-R3 independent audit

## Step 0 channel proof

Seven empty heading-only Markdown artifacts were committed remotely before substantive auditing at:

```text
0368dbc7646fc9f62df17ee8eadb2548d8fb64c2
```

The ordinary Git transport in the execution environment could not resolve `github.com`. The remote
ref and commit were observed through the connected GitHub API. The first three required commands were
then run against a local Git readback reconstructed from the observed remote commit/tree. The fourth
command was run against the actual `origin` and produced no stdout; its complete stderr is retained.

`git rev-parse research/int-r3-independent-audit`

```text
0368dbc7646fc9f62df17ee8eadb2548d8fb64c2
```

`git rev-list --count dc7bdf79a..research/int-r3-independent-audit`

```text
1
```

`git ls-tree -r --name-only research/int-r3-independent-audit | grep int-r3`

```text
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-anchor-and-citation-verification.md
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-claim-evidence-ledger.md
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-formal-argument-audit.md
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-independent-audit.md
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-orientation-error-ledger.md
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-recommended-revision.md
policy-engine/docs/research/policy-operations/audits/int-r3/int-r3-seam-and-crosscheck.md
```

`git ls-remote --heads origin research/int-r3-independent-audit`

```text
fatal: unable to access 'https://github.com/DenisKopylov/polisyos.git/': Could not resolve host: github.com
```

The GitHub API observation is not substituted for that failed command. It is an independent channel
receipt showing that the remote ref existed and pointed to the Step-0 commit.

## Verdict

# `GO_WITH_REVISIONS`

The package’s controlling negative survives: it contains no human-subject result and cannot establish
that real operators understand or safely act on the PolicyOS surfaces. The protocol is coherent and
executable in principle. No structural defect was found that bounded amendment cannot repair.

The package may not advance unchanged as a canonical design input. Its mandatory repository baseline
contains false anchors; its repository-wide absence claims are sampled rather than enumerated; its
external source chain is not independently resolvable from committed bytes; two transfer arguments
remain template-level; the four most novel constructs lack construct-specific resolution evidence;
`contestable`/`invalid` exclusions can absorb the entire hard stratum; programme execution feasibility
is not established; one staleness red can reject a correct surface; the twelve reds conflate four
property classes; the missed-blocker primary observation can be retrospective; the package misses an
existing DS6 instrument-owner allocation; and the `W4-K05` gate token turns on a local comprehension
claim rather than DS12’s first-public predicate.

The hostile pass actively looked for a reason to issue `NO_GO`: an impossible protocol, an
unfalsifiable core, a hidden institution, a benchmark whose system-specific content disappears, or a
DS12 authority grab. It found none that revision cannot repair. It also did not find grounds for bare
`GO`: thirteen material and five minor findings require amendment.

## Finding register

### Package findings

| ID | Severity | Threat | Finding | Closure route |
| --- | --- | --- | --- | --- |
| `INT-R3-AUD-F001` | `material` | T7 | Mandatory repo baseline contains a nonexistent `TrustPostureContent` anchor and an inaccurate `TimeSemanticsLabel` contract/clock description. | `RR-01` |
| `INT-R3-AUD-F002` | `material` | T7 | “No admitted human comprehension evidence,” “no canonical behavioral contract” and related repository-wide zeros were inferred from named-path search, not a complete pinned walk with denominator, executor and controls. | `RR-01` |
| `INT-R3-AUD-F003` | `material` | T3 | The sixteen `EXT-*` rows cannot be independently resolved from committed bytes: no durable per-claim URLs/DOIs/report IDs, locators or committed survey ledger. | `RR-02` |
| `INT-R3-AUD-F004` | `material` | T3 | `F005` and `F007` use “mechanism transfers; rates do not” without constructing the target operator/workflow bridge or the deterministic-min versus probabilistic-conjunction distinction. | `RR-02` |
| `INT-R3-AUD-F005` | `material` | T4 | `F008` correctly defers the four novel constructs but does not state construct-specific resolving evidence, endpoint, population, precision dependency or transport requirement. | `RR-03` |
| `INT-R3-AUD-F006` | `material` | T5 | `contestable`, `invalid` and primary-score exclusion have no coverage floor or absorption bound; logically, 100% of a hard construct/modality stratum can disappear while an aggregate score survives. | `RR-04` |
| `INT-R3-AUD-F007` | `material` | T1 | Protocol coherence is established, but programme execution feasibility is not: no recruitment frame, ethics route, accessible research support, panel staffing, pilot envelope or plausible participant × item precision plan. | `RR-05` |
| `INT-R3-AUD-F008` | `material` | T2 | `AUI-R06` treats unchanged fresh/stale affordance as universally red; a correct surface may retain the action when currentness is non-dispositive, another current basis exists, or a governed override route applies. | `RR-06` |
| `INT-R3-AUD-F009` | `minor` | T2 | The twelve reds are falsifiable but conflate surface semantics, enforcement, instrument integrity and behavioral trials; ten can pass without a real operator. | `RR-06` |
| `INT-R3-AUD-F010` | `material` | T8 | `gate_standing: NO_GO` is used for a local claim-use prohibition. `W4-K05` defines that axis as the first-public gate; DS12 does not name INT-R3 as an input. Correct token, wrong predicate. | `RR-07` |
| `INT-R3-AUD-F011` | `minor` | additional | `Bhat_i` may include blocker selection collected after terminal action/confidence, allowing post-choice reconstruction to improve the primary missed-blocker result. | `RR-08` |
| `INT-R3-AUD-F012` | `material` | T1/T7 | Package says benchmark owner is missing, while the active Atlas plan says DS6 owns the instrument and INT-R3 supplies its content. Live/stale/superseded ownership is not adjudicated. | `RR-01` |
| `INT-R3-AUD-C001` | `commendation` | T2 | The package repeatedly and unambiguously states that no human result exists and that literature cannot stand in for these surfaces. | preserve |
| `INT-R3-AUD-C002` | `commendation` | T2/T6 | Eligible-opportunity denominators, attempt-versus-commit, latency failure handling and direct high-confidence-wrong cells are unusually precise. | preserve |
| `INT-R3-AUD-C003` | `commendation` | T1/T2 | Accessible relation parity is part of the instrument, not an annex; real AT users and modality-specific timing are required. | preserve |
| `INT-R3-AUD-C004` | `commendation` | T5/T6 | Three-layer ground truth, set-valued `A_i*`, retained disagreement and explicit absence of appointed adjudicators prevent authority laundering. | preserve |
| `INT-R3-AUD-C005` | `commendation` | T3 | Source-domain rates are not imported, and NDM versus heuristics-and-biases disagreement is preserved instead of resolved by prose. | preserve |

### Orientation findings

| ID | Severity | Source | Finding | Closure owner |
| --- | --- | --- | --- | --- |
| `INT-R3-AUD-O01` | `material` | stage 2 | Audit branch was ordered from the pre-research base, contrary to pipeline §2 containment. Direct instruction obeyed; topology is nonconforming. | principal/pipeline owner |
| `INT-R3-AUD-O02` | `minor` | stage 2 | Prompt says `F001-F010` and seven of ten; committed register is `F001-F018`, seven of eighteen. | principal |
| `INT-R3-AUD-O03` | `minor` | stage 1 | Prompt calls INT-R3 Wave 5 and later “other Wave 8 tasks.” | principal |
| `INT-R3-AUD-O04` | `material` | stage 1 | Prompt says real surfaces show exactly eight constructs, while several are plan/in-flight targets rather than current glass. | principal; package corrects inherited wording |
| `INT-R3-AUD-O05` | `material` | stage 1 | Prompt supplies `20/24` and commands the repository-wide zero “no evidence anyone understands” without executor/denominator/controls. | principal; package must verify or downgrade |
| `INT-R3-AUD-O06` | `minor` | stage 1 | “Your benchmark is what would close it” ambiguously follows three DS11 debts; behavior evidence cannot close page a11y, external countersign or copy-checker coverage. | principal |

## Severity arithmetic

```yaml
finding_total: 23
blocking: 0
material: 13
minor: 5
commendation: 5
sum: 0 + 13 + 5 + 5 = 23
register_rows: 23
arithmetic_closes: true
```

Package-only subtotal:

```yaml
package_finding_total: 17
material: 10
minor: 2
commendation: 5
sum: 10 + 2 + 5 = 17
```

Orientation subtotal:

```yaml
orientation_finding_total: 6
material: 3
minor: 3
sum: 3 + 3 = 6
```

## T1–T8 disposition

| Threat | Position | Established? | Controlling finding/result |
| --- | --- | --- | --- |
| **T1 — unrunnable here** | No in-principle impossibility was found. The protocol is technically coherent; actual programme feasibility is unproven and the owner seam is wrong. | partly | `F007`, `F012`; not `NO_GO` |
| **T2 — unfalsifiable by construction** | All twelve predicates can fail. Ten are not human-behavior tests and one staleness red is overbroad. The package’s `not_established` result remains falsifiable by a future run. | threat not established in strongest form | `F008`, `F009`, `C001`, `C002` |
| **T3 — transfer template** | Four mappings are earned narrowly; `F005` and `F007` are under-constructed; `F015` is not a transfer claim. Durable source binding is also missing. | established in part | `F003`, `F004`, `C005` |
| **T4 — PolicyOS content deferred** | PolicyOS-specific integration remains, but direct evidence for the four distinctive constructs is deferred and lacks resolution criteria. | established in part | `F005` |
| **T5 — absorbing escapes** | No empirical proportion can be estimated without an item bank. The logical absorption bound is 100% of a hard stratum, and no coverage gate prevents it. | established | `F006` |
| **T6 — borrowed institutions** | The package explicitly names the missing panel/owners and forbids impersonation. Denominators cannot be issued today for contestable policy items, but the dependency is not hidden. | hidden-dependency hypothesis not established | `C004`; acceptable residual |
| **T7 — baseline absences** | Key zeroes are sample-derived; two positive anchors are wrong; supplied historic counts are correctly labelled supplied. | established | `F001`, `F002`, `F012` |
| **T8 — DS12 boundary** | INT-R3 is routed to DS6’s interactive-surface stable bar, not DS12’s gate. Package non-use rule is right; `gate_standing` predicate is wrong. | established | `F010` |

## Final readback

The final remote readback must occur after this file’s commit exists; this artifact therefore does not
pre-claim its own final commit SHA. The controlling final four command outputs and the API-observed
remote head are reported in the stage-2 hand-back after the final write. If `ls-remote` remains blocked,
its complete stderr is reported instead of a fabricated value.
