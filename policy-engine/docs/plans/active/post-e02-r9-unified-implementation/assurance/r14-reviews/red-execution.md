# R14 execution allocation red-team

Baseline: `c8986d035f12c1c3d9e5d0d57e369fe8257bccbc`. Scope: current R14 task allocation and handoffs only. Read-only review; no product code, tests, installs, imports, or builds.

**Verdict:** The 109 baseline task records remain present and their acceptance fields (`deliverable`, `positive`, `adversarial`, `removal`, `surface`, and `final_execution_property`, where present) are semantically unchanged. The 10 added DES tasks each map to one R14-DES-01..10 obligation; they remain planned/UNRUN and are not presented as closure. Allocation reuses the named N4, N6, search, memory, Lex, document, gateway, and evaluation owners. The one issue below is a pre-dispatch write-allocation gap.

## Finding

### MEDIUM — DES-01/02/09 shared writer is not consistently allocated

**Section:** `tasks.json` DES-01, DES-02, DES-09 (`9898–9925`, `9983–10008`, `10580–10605`); `solutions/13-productive-design.md` DES-01 composition (`23`) and DES-09 steps/composition (`382–390`).

**Evidence and consequence:** DES-02 and DES-09 both list `runtime/quality/hypothesis_ledger.py` and `scientist/policy_design/formulator.py` as write candidates. DES-01 also lists `formulator.py`. DES-02 uses canonical lease keys `write:hypothesis-ledger` and `write:design-intent-formulator`; DES-09 lists neither the former nor the same formulator key (it says `write:design-intent-formulator if changed`). DES-01’s one-writer note names DES-02/08 but omits DES-09, while DES-08 does not own the formulator path. DES-02 can prepare against DES-09’s interface, but that agreement does not select which task owns these shared files. The generic exact-path rebind rule prevents dispatch before reconciliation, so this is a planning/dispatch blocker rather than evidence of a live source race. The plan therefore cannot certify independent writes to these files; it must hold the overlapping paths until P0 assigns a writer and handoff.

**Smallest fix:** At accepted-source rebind, assign one writer per shared path and make the others consume a versioned interface. For example, DES-09 can own invocation/context receipts in `prompt_tool_ledger.py`, with a stable receipt ref; one selected candidate owner binds that ref into `hypothesis_ledger.py`. Normalize the exact lease key for `formulator.py` and name DES-09 in the one-writer rule, or remove its write claim there. Preserve independent interface preparation on disjoint paths.

**Falsifier:** This finding is cleared if the P0 path map shows one named writer and exact-path lease for `formulator.py` across DES-01/02/09, and either DES-09 is read-only on `hypothesis_ledger.py` or its mutation is routed through the single candidate-ledger owner; a fresh N4 consumer must resolve the persisted invocation ref. Otherwise keep these overlapping path writes undispatched until the owner map is corrected. Pattern: P27; bridge handoff also touches P02.

## Verified allocation and dependency properties

- DES-02 is the N4 generator; DES-04 is the N6/N7 bridge writer. DES-03 owns native numerical search and consumes GYD-30/31 outputs. DES-08 shares `search.py` with DES-03 under the same `write:scientist-policy-search` lease; DES-08 owns retrieval adaptation and leaves lineage to LIF-07. No second optimizer, controller, or memory store is claimed.
- Legal roles are separated in the plan: CAP-05 supplies source/relation proof; CNT-04 supplies selected case evidence/data/config and says it makes no shared runtime writes; DES-05 owns generic Lex/Scientist interpretation composition. All reference `lex/normpack/applicability.py`, so P0 must assign that exact path once. The design text explicitly requires one exact-path writer and does not allocate a second legal store. This is a rebind condition, not a separate finding.
- DES-06/07 use the same document-owner and generated-family lease keys. DES-06 owns producer/schema/export; DES-07 owns import/edit through an agreed shared schema. DES-07’s edge to DES-06 is `interface_agreement`, allowing preparation before render completion.
- DES-09 reuses the traced gateway, prompt/tool ledger, and CAP/LIF/OPS rights/resource owners; it does not claim a second gateway or budget service. DES-01/02/03/04/05/07/08 also have interface-stage overrides on their named upstream edges, permitting scoped preparation while actual producer outputs remain necessary at composition. DES-06 permits bounded independent preparation.
- No freeze/replay cycle is present in the task-stage split: DES-10’s recipe/oracle readiness may precede freeze; its composed comparison runs in `FINAL-REPLAY` after `FINAL-REVIEW`. `FINAL-FREEZE` includes DES-01..10 readiness, `FINAL-REPLAY` accepts DES-10 in the same wave, and `FINAL-USE` follows replay. The comparison therefore has one final wave and does not demand its own result to pass its preparation gate.
- Pattern pass: P01/P02/P27/P31/P35/P38. The task criteria provide positive, adversarial, and removal signals; they distinguish actual emitted/consumed outputs from markers and retain the original inventory. All R14 obligations are separately accounted for, with unavailable live/audience results left explicit.


## Narrow delta rereview — canonical writer allocation

**Result: the MEDIUM writer-allocation finding above is closed by the current task/solution/conflict/workstream edits.** A complete `tasks.json` walk of `canonical_write_candidates` assigns `scientist/policy_design/formulator.py` only to DES-01, `runtime/quality/hypothesis_ledger.py` only to DES-02, and `runtime/quality/prompt_tool_ledger.py` only to DES-09. Their canonical lease keys match those owners; DES-09 additionally owns the native context projection path selected at accepted-source rebind. DES-02 and DES-09 retain formulator/ledger paths only as read-only anchors, and their `r14_canonical_writer` statements route requests to DES-01/DES-02.

The same assignment is repeated in the DES-01/02/09 solution-card metadata, the `n4-intent-hypotheses` and `llm-context-rights` conflict groups, `solutions/13-productive-design.md`, and `workstreams/07-productive-policy-design.md`. The conflict-group resolution explicitly leaves independent preparation on disjoint files. The task lease rule says `resource_locks` are descriptive and exact shared paths take precedence; the remaining descriptive formulator labels on DES-02/09 therefore do not create independent write leases under the manifest semantics. The context projection's concrete path is intentionally pinned at P0; current conflict mapping gives its write to DES-09 and keeps CAP/LIF/OPS as contract suppliers.

**Falsifier checked:** another task's `canonical_write_candidates` includes any of the three concrete paths, or DES-02/09 claims writable ownership of its read-only supplier paths, or the context path resolves to a separate writer. None is present in the current planning snapshot. This clears the earlier overlap finding; it does not claim implementation or runtime verification.
