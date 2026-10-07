# B201/B202 IR consumer map

Read-only source map for the human-scoped E appointment. It identifies actual producer, persistence, readback, law-computation, and summary-consumer paths; it does not ratify the four choices, accept C/F work, or close either finding.

## Pins and evidence

- G integration source: `9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`, tree `f27a36aa7eae9d6e329e0602ea40b6169a5bcf35`.
- Historical E PR38-r2 packet: `origin/codex/e02-E-continuation-20261006@8e7e6cc28ac336fa9275ed456ac19a74d0e55553`, tree `4b062f4fe79c311b887e1f050cde1432d8a31830`, `implementation-handoffs/E/continuation-20261006/pr38-r2/ir-semantic-owner-decision.json`. It says `canonical_owner:null`, `decision_state:unratified`, `ledger_status:held`, and that no v2 wire semantics were implemented in that packet.
- C source candidate: `48af851db5c0e802c92d9b30226acbc4436c69ba`, tree `84b6416c9cc84a975ceb2d5d4cd5a8a4f6b3d9e2` (source census recorded in `integration/reviews/2026-10-07-all-six/C.md`).
- F causal/ConfidencePass source candidate: `8236d9c368336a5ea20c1586f29aea7321db6536`, tree `724a77c88d4e6699ffead58a5e3e3990fb88640a`.

## Existing IR writer, persisted shape, and law consumer

At G `9a187` (`src/polisyos/ir/analytics/uncertainty.py`, blob `0a2495855d707a6548da6983bdef9abed9c4b0c7`), `PosteriorSamplesCarrier` (lines 557–580) holds one vector of finite samples, an axis label defaulting to `draw`, and optional nonnegative weights. It has no draw-row identifiers or typed shared-law identity. `UncertaintyEnvelope` (1357–1388) holds a point, interval, family/source/semantics, optional distribution payload, and arbitrary metadata.

`persist_uncertainty_envelope` (2115–2133) writes that model as `ir.uncertainty_envelope` JSON, default schema 1.1, and returns the generic `UncertaintyEnvelopeRef`. `load_uncertainty_envelope` (2136–2142) fetches by artifact ID and validates the same model. This path has no joint-law-specific reference, resolver, codec, or migration. The existing reader is therefore a real v1.1 persisted-envelope path; the E packet's proposed distinct v2 `$id` is only a proposal, not current behavior.

The actual numerical joint-law consumer is `foundry/uncertainty/monte_carlo.py` (`_build_empirical_joint_spec`, lines 158–249; `_sample_from_envelope`, 1258–1319). For multiple parameters it requires a common `metadata["joint_sample_id"]`, matching axis/sample count and normalized weights, then applies shared sampled row indices to each parameter vector. This computes from aligned rows; it is not a display-only read. However, the shared ID is a string assertion and there are no content-bound row IDs/resolution in this path (P37/P38 boundary: declared ID plus matching shape is the tested predicate, not independently verified row identity). E should decide whether the original B202 criterion requires a stronger carrier and bind the falsifier to the real sampler.

The current calibration producer is not a raw posterior-draw producer: `Calibrator.run` calls `envelopes_from_calibration` on Hessian uncertainty (`foundry/calibration/calibrator.py`, 1777–1817); `envelope_from_calibration_param` makes a non-gating local-Gaussian interval from projected covariance (`foundry/calibration/uncertainty_adapter.py`, 49–161). The separately exported `summarize_bayesian_calibration_posterior` computes an unweighted mean/interval but emits no sample carrier and has no production `src` caller in the pinned G source. Do not claim a live calibration-draw-to-joint-sampler chain from that helper.

The orchestration bridge `scientist/nodes/builtins/simulate/propagate_uncertainty.py` reads snapshot envelopes or inline/ref envelopes from `CalibrationReport` (283–317), calls `PropagationDispatcher` (118–143), persists output envelopes (177–202), and updates `SimulationResult`. That is the actual read/compute/write bridge for simulation propagation; its output is not itself an E semantic ratification.

## C and F boundaries

**C:** The C candidate's changed paths in `fabric/data_plane` are `README.md`, `modes.py`, `schema_rows.py`, and `streaming.py`; its changed code modules are the latter three. The complete changed-source list contains no IR uncertainty writer/reader or law consumer. C owns its streaming/data-plane consumer work; this review found no C B201/B202 law consumer to appoint. This is a bounded statement about the candidate, not a claim that no unrelated IR consumer exists anywhere in the repository.

**F:** At F `8236`, `scientist/nodes/builtins/simulate/run_causal_evaluation.py` derives an envelope from `CausalEffectReport.to_uncertainty_envelope` and persists it through the generic v1.1 writer. In `ir/analytics/causal.py` (288–357), that projection is point estimate + interval + family/metadata; it supplies no posterior/joint sample payload and sets `gate_eligible=False`. It is a causal summary projection, not a joint-law producer.

F `scientist/governance/passes/confidence_pass.py` loads those refs and checks CI width/point ratio, absolute width, and the gate-eligible ratio (F source blob `8e16e8d76aeb8f4efe05589c1e084111d4479ee7`). It does not read samples/weights or calculate posterior means/quantiles/covariance: this is a summary threshold consumer. F's eighth-wave review records separate bounded producer/fresh-CAS-reader and ConfidencePass issue-preservation evidence, but no single TMLE-produced envelope is fed through ConfidencePass with a corrupt sibling SimulationResult (`integration/checks/2026-10-07-eighth-wave/reviews/F-causal-confidence.md`, lines 16–22).

F `8236` is not the current G implementation of ConfidencePass: G `9a187` has blob `92b3175c93a9b35c543456a8f107153ce42798bf` (delta from F's blob above). G removed the early causal-purpose blocker and returns only the simulation-load warning on that sibling-load failure path. Thus F's bounded issue-retention evidence must not be reported as current G behavior. This is an F/G consumer delta, not an E appointment to repair F.

## Appointment limits and owner action

The human direction is recorded in `_build/e02-g-continuation-20261006/R/cleanup-20261007/B201-B202-E-appointment.md` and `.json`: E is the accountable semantic and implementation owner **only for B201/B202**. E should verify v1.1 sufficiency first, preserve v1.1 replay, choose a new version only if the original criterion requires it, and compare CAS-only with inline-plus-ref against the actual writer/readers/sampler. E may record the four finite choices in its own tracked ratification. The packet's recommendations are not pre-approved semantics.

E does not inherit every IR/public API concern, rewrite the historical unratified packet, assign or accept C/F consumer work, or claim scientific/institutional authority. C retains its data-plane work; F retains its causal/ConfidencePass implementation and evidence. B201/B202 remain held pending E's decision, exact producer/readback/sampler evidence, independent review, and formal adjudication. No tests were run for this source-map task.
