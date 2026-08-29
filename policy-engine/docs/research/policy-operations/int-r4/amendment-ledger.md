# INT-R4 — Stage 3 Amendment Ledger

Amendment stage: `stage_3_amendment`  
Package head answered: `c3999897b5be2308513846935f1c4fb68157bcb3`  
Audit head answered: `ea2eac5575e5b8fb4a5462c068a37bb913076952`  
Amendment branch: `research/int-r4-ops-r5-amendment`  
Joint pair: `INT-R4` with `OPS-R5`  
Ledger ownership: this file owns `AUD-F01`, `AUD-F03`, `AUD-F04`, `AUD-F05`, `AUD-F07`,
`AUD-F09`, `AUD-F10`, `AUD-F12`, `AUD-F13`, and `AUD-F14`. The OPS-R5 ledger owns the other
eight findings. No finding is duplicated between ledgers.

This ledger is an append-only amendment record. Where it expressly supersedes a stage-1 statement,
the superseding rule below governs the amended package. It does not edit or reinterpret an audit
artifact, confer authority, register a type, appoint a person or institution, or lift the audit verdict.

## 1. Standing And Non-Effect

The standing vector remains:

```yaml
research_standing: accepted_narrow_scope
capability_standing: absent/unallocated
gate_standing: NO_GO
audit_verdict: GO_WITH_REVISIONS
```

Stage 3 responds to findings. It does not create a capability or convert the audit's target verdict
into an observed `GO`.

## 2. `AUD-F01` — Absorbed OPS-R7 Discharge

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:107`.  
Disposition: `accepted`.

A field that records a version or exposure history is not a causal-validity rule. The seven questions
identified by the audit are discharged below with an estimand, admission conditions, failure mode,
falsifier, and honest residue.

### 2.1 OPS-R7 closure matrix

| Absorbed question | Amended rule | Admission evidence and assumptions | Failure or falsifier | Unresolved residue |
|---|---|---|---|---|
| Repeated looks and stopping | Every confirmatory comparison names a prospective look schedule, information basis, stopping rule, and error-control method appropriate to the design. An unscheduled outcome-driven look cannot support a confirmatory update and is retained as exploratory evidence. Crossing a stopping boundary may change exposure or trial continuation, but does not by itself make the stopped effect-size estimate unbiased. | Immutable schedule or charter; look number and information fraction; multiplicity or always-valid error-control record; unchanged outcome, population, version and analysis definition. | A consumer reaches the same confirmatory result after deleting the schedule, changing the look after seeing outcomes, or treating an early stop as final effect-size calibration. | No universal stopping method transfers across domains. The design owner must select and justify the method before deployment. |
| Endogenous version assignment; sequential exchangeability and positivity | Causal comparison across versions is admitted only under prospective randomization, or under a declared longitudinal identification model in which sequential exchangeability, consistency and positivity are argued at every decision point using the full measured history that triggered adaptation. If a bad outcome itself changes the next version and the adaptation trigger is not fully controlled, version comparison is association-only. | Assignment mechanism; decision history `H_t`; version propensity or randomized probability; support/overlap diagnostics; complete adaptation-trigger and concurrent-intervention record; censoring model. | A version effect survives after removing the adaptation trigger, positivity evidence, or assignment record; or a deterministic high-risk route is represented as if all units could have received all versions. | Unmeasured adaptation triggers and structural non-positivity cannot be repaired by more rows from the same deployment. They remain `not_established` or require a new design. |
| Carryover and treatment history | The treatment object is the complete exposure sequence, not the current version label. Every estimand declares the relevant lag, washout, persistence and interaction assumptions. If prior versions can affect the current outcome and their effects cannot be separated, the admissible object is a sequence or dynamic-regime estimand, not a current-version effect. | Versioned exposure start/stop, dose/intensity, prior states, lagged outcomes, concurrent interventions, and a subject-matter carryover model or design-based washout. | Two units with the same current version but materially different histories are treated as exchangeable; deleting pre-current exposure history leaves the result unchanged. | Unknown long-tail carryover is a structural identification gap. The package specifies refusal or bounds; it does not invent a washout horizon. |
| Version-specific versus mixture versus dynamic-regime estimand | Use a version-specific estimand for a claim about one named `A_v`; a mixture estimand only when the target distribution `g(v)` over versions is itself declared and stable; and a dynamic-regime estimand when the intervention is a rule `π(H_t) → A_t`. Ambiguity among these objects makes the comparison unevaluable. | Exact claim object; version and rule identity; target population; exposure distribution; assignment history; intended versus realized regime; policy rule effective dates. | Changing the version distribution or decision rule leaves the claimed estimand identity unchanged; a mixture is reported as a single-version effect; or an adaptive regime is analyzed as a static treatment. | There is no domain-independent preferred estimand. Selection is claim-specific and must precede outcome inspection. |
| Pooling or equivalence across versions | Evidence for `v` never transfers to `v+1` by default. Pooling requires a predeclared equivalence claim over every causally material dimension: intervention content, eligibility, dose/exposure, decision rule, outcome definition, measurement pipeline and relevant context. The equivalence margin and test are fixed before observing comparative outcomes. | Content diff; bridge or dual-run evidence; version-by-effect interaction assessment; equivalence margin tied to the claim; exposure comparability; unchanged or explicitly bridged measurement. | Any material dimension changes without a bridge; the version-by-effect interaction exceeds the bound; the bridge fails; or removing the equivalence evidence still preserves the old claim. | Equivalence cannot be inferred from “small code change”, common name, overlapping confidence intervals, or absence of detected difference. |
| Unplanned adaptation: reset versus downgrade | Every unplanned adaptation creates a new version identity. A change to the causal object—construct, eligibility, exposure, decision rule, outcome, measurement relation or mechanism—resets confirmatory status for the changed object to `exploratory_only`. A bounded operational change may move the prior claim to `under_review` rather than reset it only when prospective equivalence evidence proves the claim object unchanged. | Classified version delta; claim dependency map; equivalence evidence; prospective decision record; affected population and exposure history. | A materially changed version retains `confirmatory_intact`; or a harmless operational change is declared equivalent solely by author assertion. | Whether a specific delta is causally material is domain evidence, not a repository-wide default. |
| Version-specific exploratory-to-confirmatory promotion and multiplicity | Promotion is a new prospective test: freeze the version or dynamic rule, estimand, endpoint, population, horizon, analysis and multiplicity family before collecting promotion evidence. Evidence generated while discovering the hypothesis or selecting the version stays exploratory. A later version does not inherit the promotion result. | Frozen promotion record; prospective sample/evidence start; version-specific analysis plan; family definition and multiplicity control; independent or design-based evidence; immutable history. | The same observations select and confirm a hypothesis; endpoints/subgroups/windows change after results; or `v+1` inherits `v`'s confirmatory status without a new test or valid equivalence bridge. | Production error rates and promotion thresholds remain domain-specific and are not selected by this amendment. |

### 2.2 Consequence for the amended package

The stage-1 statement that OPS-R7 was covered by retaining version and exposure fields is narrowed:
those fields are necessary but not sufficient. Any later architecture must implement the rules above
or continue to report the absorbed task as incomplete. No causal update may rely on a version comparison
whose estimand, assignment, history, stopping and promotion conditions are not established.
