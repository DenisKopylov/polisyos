# C40 author receipt reconciliation

The adjacent `receipt.json` preserves the cloud author's report. Its two reported
pytest PASS results have no delivered deciding outputs or final-run/source binding;
they are **author reported, not independently verified runtime PASS**. Ruff was a
tooling ERROR in that environment. No production-invocation decision was received.

The receipt's `artifact_view_identity` is a comparison **recomputed over supplied
ArtifactRef fields**, not an independent CAS/source/provenance reconciliation. The
new selected-parent/real-child tests and engine-producer witness require their own
post-composition runs before any claim of verified execution. Their scope is the
actual persisted workflow sidecar and propagation of a supplied invalidation in a
finite test; they do not establish a complete source readset or an event authority.

The sidecar projects `WorkflowSpec.depends_on` scheduling prerequisites. A child may
not consume all prerequisite outputs, and an undeclared state or external CAS read
may still affect it. Public redaction also prevents treating this projection as a
complete private lineage. Declared node reads and provenance prerequisite outputs
are useful observations, not a complete observed readset. Empty or omitted events
therefore cannot establish currentness.

The G27-02 / original `B13@RES-03` producer → durable revision/event head → fresh
SimulationResult consumer and its retained-reference removal witness remain
`bridge_missing`, `consumer_missing`, `verification_missing`, and
`semantic_test_missing`. This result does not reopen the historical independent
later-failure acceptance and is neither G acceptance nor formal closure. Source
receipt and new tests are proposals pending independent review and execution.
