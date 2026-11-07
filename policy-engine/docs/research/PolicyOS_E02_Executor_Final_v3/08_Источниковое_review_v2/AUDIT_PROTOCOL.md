# Audit protocol after source freeze

Read WORK_CONTRACT.md and catalog/criteria_catalog.json, including all 70 criteria. Complete original source-grounded records remain available. The frozen catalog is identified by catalog/FREEZE.json and SHA-256 8c8c77e13d9151349b7410b441f97f0f94fbfb7d097150f32c9872fe35a3cb59. Research is complete; no E02 finding is predetermined.

## Target and non-target

P is baseline/PolicyOS_E02_Review_and_Specs_v2 under e02_source_based_review. Audit the CURRENT root packet MD files in 02_Пакеты and companion JSON in 04_Трассировка, together with applicable general rules, lane overviews, shared contracts and integration bindings. Do not read the historical 07_Техническое_review/baseline v1 snapshots as the current target. Most previous findings were already addressed in v2; do not recycle them without a surviving issue.

The repository baseline is 20d9009be21097bfbdc38a546a15cc60213b8ace. Inspect relevant code when needed to establish a real route, precondition or counterexample, not as an unbounded new repository audit. No product/specification edits, installs, native execution or external mutations are permitted. Write only your assigned audit outputs.

## Complete criterion coverage without needless repetition

For every assigned packet, each of the 70 criterion IDs must occur exactly once in criterion_groups:

{
  "packet_id": "...",
  "lane": "...",
  "md_sha256": "...",
  "json_sha256": "...",
  "criterion_groups": [
    {
      "criterion_ids": ["RA-01", "..."],
      "status": "addressed|bounded|gap|not_applicable|unresolved",
      "reason": "Substantive reasoning specific to this packet",
      "evidence": [
        {"path": "02_Пакеты/....md", "locator": "REQ / TEST / section", "claim": "Why this addresses or fails the risk"}
      ],
      "finding_ids": []
    }
  ],
  "verdict": "...",
  "read_scope": "..."
}

Group IDs only when one actual reason and its evidence cover them. Separate criteria when their conditions differ. Generic keyword-based N/A or PASS is not review.

- addressed: the specification defines adequate behavior and future evidence; not a product PASS
- bounded: an explicit, legitimate scope, decision or qualification limit; not automatically a defect
- gap: a concrete finding is required
- not_applicable: explain why the trigger is absent at this owned boundary; higher-level ownership may be cited
- unresolved: evidence is insufficient and must not be relabeled as covered

For scenario/lane review use the same structure with scenario_id or lane_id. Cover all 42 canonical scenarios, including the four stories, and all 12 lane overviews. Cross-lane findings can link several entities without being counted repeatedly.

## Reading and establishing findings

Read the full assigned solution and test document, companion semantic fields and relevant unique metadata. Recover truncated output. Read shared rules and scenarios before declaring an omission. Record exact code ranges where inspected. Source citations must support the criterion, not decorate a conclusion.

Each finding identifies:
- the exact current v2 proposition and applicable criterion IDs
- whether the issue concerns a contract, solution, test, boundary or optional improvement
- a realistic counterexample satisfying declared preconditions
- what current local and shared tests would miss
- impact, confidence, preferred bounded correction and alternatives
- preservation obligations and a discriminating acceptance proposal

General guidance alone does not establish an E02 defect. Risk outside the claimed scope is bounded or not applicable, not a new mandatory subsystem. A requirement may already forbid a bad implementation while the tests fail to distinguish it: label that a test gap, not a missing requirement.

Preserve good existing solutions. “What, not how” does not delete implementation guidance. A compound requirement is not defective merely because it is long. Do not demand all-platform support, global exactly-once/order, eternal deduplication, arbitrary power/SLO targets or full CI per packet. Check activation, environment, exclusions and ownership. A counterexample cannot depend on a forbidden input or unsupported backend.

## Outputs

Within your assigned audit folder create:
- review.md in Russian, with a substantive verdict for every assigned packet or lane/scenario
- assessments.json with complete 70-by-entity coverage using grouped rows
- findings.json with stable group-prefixed IDs, evidence and specific correction proposals
- coverage.json with exact input hashes, read ranges, limitations and consulted sources
- progress.json while work remains

Save incrementally after each packet or meaningful group. Product/native tests remain NOT_RUN. Small independent standard-library calculations are allowed but are not product execution. Do not change the baseline or a proposed edition during this initial audit; the parent will triage findings separately.

## Completion condition

Every assigned entity has been read and assessed against all 70 criteria. Findings have been checked against the complete applicable v2 contract and shared scope. IDs, sources and persisted artifacts are verified by readback. There is no quota of new defects. Record already addressed risks and sound decisions too, and stop unrelated exploration when assigned coverage is complete.
