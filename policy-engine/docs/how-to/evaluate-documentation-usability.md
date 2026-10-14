# Evaluate documentation usability

Use this protocol to find whether a reader can answer a real project question from the handbook, cite the right evidence, and understand its limits. It is a small formative study, not a statistical claim about every reader or document.

## Prepare a session

Run four tasks with three to five readers who represent different levels of project familiarity. Include at least one reader who has not worked in the area being tested. Use the same handbook build or checkout for every participant and record its immutable documentation commit, the published URL or local source, and the separate product-source commit relevant to implementation claims. Do not compare answers across changing builds.

Ask for consent before taking notes. Record an anonymous role label, not a name or sensitive project information. Let readers use the handbook's normal navigation and search. Do not show them the scoring criteria, point to a page, suggest search terms, or correct an answer during a task. Randomize task order across participants. If someone cannot answer, record that outcome and move on.

The facilitator should record elapsed time with a monotonic timer, from the end of the task prompt until the reader gives a final answer or stops. Count a backtrack each time the reader returns to a previously visited page. Also record pages opened, search queries, dead ends, the answer's evidence links, confidence from 1 to 5, and any hints. A correct answer without support from the handbook is not a successful documentation task.

## Reader tasks

Read each prompt exactly as written. Keep the criteria in the next section hidden from participants.

1. **Current capability:** “A product owner asks whether PolicyOS can already run a complete policy analysis and justify a recommendation from end to end. Use the handbook to explain what exists today, what is a design target, and what evidence or bridges remain missing.”
2. **Source drift:** “You changed a code area named in a handbook map, and a source comparison reports drift. Find what you should review before changing the map's source pin, and explain what a clean comparison would establish.”
3. **Documentation change:** “You have been assigned a documentation-only change to a published page. Find the contribution route, the owner or escalation path, and the checks appropriate to that change. Explain what their results would not prove.”
4. **Gate claim:** “A reviewer says that a successful documentation gate proves every local link in the published site works and that the text matches the current E02 implementation. Check that claim and explain which evidence would be needed.”

## Moderator scoring criteria

Score the answer from cited handbook material and the source pins visible in the tested build. These criteria describe the current documented snapshot; re-check them against a frozen E02 source before reusing the study after integration.

| Task | Correct answer must establish | Handbook route to inspect |
| --- | --- | --- |
| Current capability | The handbook says the system is not yet functional end to end. A ratified boundary or north-star target is not implementation evidence; current maps describe selected source paths and missing bridges. A cited test name or tutorial does not prove a completed policy-analysis or publication chain. | [`docs/index.md`](../index.md), [`explanation/architecture.md`](../explanation/architecture.md), [`explanation/end-to-end-data-flow.md`](../explanation/end-to-end-data-flow.md) |
| Source drift | The checker compares the complete declared tracked path/glob set by bytes and Git mode at two immutable commits. It does not establish that the declaration covers every claim, that the prose is true, or that tests/runtime/deployment are current. The E02 snapshot records drift in five of six selected maps at the cited comparison commit; a mismatch calls for owner review after a canonical integration freeze, not an automatic pin bump. | [`reference/documentation-verification.md`](../reference/documentation-verification.md), [`reference/e02-documentation-snapshot.md`](../reference/e02-documentation-snapshot.md#source-drift-in-handbook-maps) |
| Documentation change | Contributors are routed through the documentation-only workflow, style guide, task owner and the checks selected for the changed surface. For published pages, style, accuracy/freshness and strict build have separate scopes; a command recipe or green check is not a receipt for unrun checks and does not prove claim truth. | [`reference/contributor-start-here.md`](../reference/contributor-start-here.md), [`reference/ownership.md`](../reference/ownership.md), [`reference/documentation-verification.md`](../reference/documentation-verification.md) |
| Gate claim | The path-aware gate is selective and stops after its first failed child. Accuracy checks a declared Markdown/publication subset; strict MkDocs build is not complete link validation. The rendered-link checker is standalone and checks only its supported local file and HTML-fragment forms in emitted HTML/CSS; external liveness, browser behavior, unsupported forms and non-HTML fragments remain outside its proof. Neither gate nor source-byte equality establishes E02 semantic currentness. | [`reference/documentation-verification.md`](../reference/documentation-verification.md), [`reference/e02-documentation-snapshot.md`](../reference/e02-documentation-snapshot.md) |

Score answer quality separately from whether the handbook contains usable material: **2 — complete and supported** (all critical points are correct and cited); **1 — partly correct** (some useful evidence, but a key limit or route is missing); **0 — incorrect or unsupported**. For the source-drift and gate tasks, a confident claim that the documentation proves current runtime/E2E behavior is a critical error even if other details are correct; cap that task at 0.

After the session, assign exactly one outcome code for each task. Do not infer an outcome from the score, elapsed time, or a participant's confidence:

- **FOUND** — the reader located and cited material that directly addresses the task; score whether they interpreted it correctly separately.
- **MATERIAL_ABSENT** — review of the tested documentation snapshot confirms that adequate, authoritative material for the task is absent.
- **NOT_FOUND** — adequate material is present in the tested snapshot, but the reader did not locate or cite it.
- **NOT_ESTABLISHED** — the reviewer cannot reliably distinguish absent material from a findability failure, or the tested snapshot/evidence is incomplete.

Use `NOT_ESTABLISHED` whenever the distinction is uncertain. A low score alone does not establish a documentation gap, and an unanswered task alone does not establish a navigation problem.

## Interpret the results

Treat this sample as a way to identify repair work, not as a benchmark score. Fix any path that leads a reader to a materially false claim about authority, implementation status, E02 freshness, or test execution. Investigate a repeated dead end or wrong page route when it appears for two or more readers. A fast answer with weak or misleading citations is not an improvement.

After a navigation or wording repair, repeat the affected task with at least one reader who did not see the earlier version. Keep the old and new handbook commit pins with their results. Do not describe an agent walkthrough, author review, or source search as a human usability test. Do not use this protocol to claim the whole repository is easy to use; record the exact audience, tasks and content snapshot.

## Session record

Copy this compact record into the review or issue that owns a study. Keep personal identities and private recordings out of the repository.

```text
Study date:
Documentation commit / URL or checkout:
Relevant frozen product-source commit:
Readers (anonymous role labels and prior familiarity):
Task order per reader:

| Reader | Task | Outcome | Score (0–2) | Seconds | Pages opened | Backtracks | Search queries | Dead ends / hints | Confidence (1–5) | Evidence cited |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- |

Repeated failure paths:
Critical misunderstanding:
Change proposed and owner:
Human sessions run: YES / NO
Limitations of this sample:
```

## Initial desk preview

**2026-10-14 — agent desk preview only; no human sessions, participant timing, or blinded test.** Starting from the handbook index, the current-capability question is answered directly by the end-to-end disclaimer and can be supported by the architecture and data-flow maps. The source-drift question routes through the E02 snapshot and documentation-verification contract; it requires opening both to distinguish the observed five-of-six map drift from what source-byte equality proves. No backtrack count or elapsed time was captured. This preview identifies candidate routes only and is not usability evidence.
