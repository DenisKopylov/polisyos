# V5 configured Search GP plateau oracle — R13

Date: 2026-10-12. Status: virtual, unapplied test-and-documentation proposal. Physical source checkpoint at freeze: 9dd15d1c1bc89d189a5c53c47e816ce48ab5b352, tree 1955e110ad48276702acbcc061761268d3e41d50. This delta changes one native integration test and its README/release/decision companions. It changes no estimator, optimizer, artifact schema, public API, or authority rule.

## Original criterion and scope

The configured V5 task is docs/research/e02-cloud-test-plan/execution-prompts/unified-local-2026-10-09/TASKS.json@a37c75cfe09d33c1f50379d5bbfd04bdb728c990e832aec3bf19c0d17035734c#/tasks/V5; its exit criterion is “exact context/history/quantity/CAS path; selected GP/native/injected evidence separately graded.” The source-work quantity requirement is separately stated at docs/research/e02-cloud-test-plan/integration/connected-closeout-plan-2026-10-08/06-inputs-and-deferrals.md@afafcd97ebbc1e68abc1ed555853f269d566dc2a6e97389b414007f17394802c#D-B157: actual draw/sample/work counts, candidate/input/seed/profile refs, and persisted outputs, with configured/requested counts insufficient.

Neither criterion requires unique estimator outputs for unique configurations. The old assertion len(set(observed_ate_values)) == 4 was an extra test oracle, not an accepted scientific contract. R13 changes only this assertion’s semantics while retaining four actual measurements, full source and execution refs, effective parameter binding, and fresh CAS reads.

## Deciding R388 witness

The retained root run is docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/b61-b161-v5-actual-composed-focused-r388-20261012/. Its command receipt is command.json@9fbfd6088d2c27ab2bf8a9b7526b92e653d7dd9a2614040bff5f56368741c989, stdout is stdout.txt@d09d17a9be35a8e886540cfa7a9f8f598c90c1fdc7173be6fce110d01861e5b3, and JUnit is junit.xml@df40d062d97543e0da382274ef2f67b72d69de1e727a6e5bdb68d8c0db703eb2. The focused wave had 124 cases: 104 passed, 13 failed, and 7 errored. This target failed only after completing its four evaluation/ref/packet/result reads, at the assertion demanding four unique ATEs. The proposed R13 test has not yet run.

The controlled CAS objects under fixtures/test_native_gp_methodjob_searc0/cas/artifacts/sha256/ show four distinct candidate coordinates, evaluation refs, MethodResult refs, and work-packet refs. Every job used the same persisted 40-row synthetic source and actual 40 completed bootstrap draws. Each evaluation remained non-promotable. The selected coordinate is the actual propensity_clipping passed to the DR method:

| Order | Selected clipping | Clipping fraction | Persisted propensity support | ATE | Proposal source |
| --- | ---: | ---: | ---: | ---: | --- |
| 1 | 0.45082398414611818 | 1 | 0.45082398414611818–0.45082398414611818 | 0.95800692250672836 | sobol_init |
| 2 | 0.028002403974533081 | 0 | 0.37499999999999994–0.4375 | 0.96592622156327701 | sobol_init |
| 3 | 0.26055227666199676 | 0 | 0.375–0.4375 | 0.96592622156327701 | random_insufficient_data |
| 4 | 0.15941798434475968 | 0 | 0.37499999999999994–0.4375 | 0.96592622156327701 | bayesian_acquisition |

The four full evaluation refs, listed as artifact ID @ selected manifest-profile SHA-256, are:

1. c3e5cb8939a17b14bf9ff11fc6e5e4c2ee8196d1155fc9fd5b510b313b7b04ec@04d9b92ee1a2378d0cffc03a532577be5846963630c693df76bde1e869e9c173
2. 6c9e2cb965a5237f715b652f68eacdfc2b9a6bc01c0a7836f21fbf3bcdda0a71@eff08548ed1b1576c0f85b9721ffca3f43c97d9f0ed0bdfdbf778f292cddd767
3. fda16af0d47615408c91f08994bb2f22b5587f522458c09177710c8bd9a63c1d@52250f890d395dd68083e1e457fba43d411a87a65e9db8a7e47cc36c8260a6c1
4. 09f47657a6735414768fbccc5ee34401ee60a1ac0d99bba9e988c9b204903c77@21356781a0f8c73a59fde32c4bf892b5a3ab0529cd5e9db3d7f06dc0b99263d5

The method-result artifact IDs, in the same order, are 8c36c405b2de6dbd4485d21a98953e714bf6562d7c0375e9ca5bbd8ce00d9c17, 8d12e84d8614d17e4c3b9d7ded81ae8aa87adf8b898ef3d47a876f6c96d1cf63, 1fbe853c9afcc8ec04fc50edc296641349dfad8c761930fe5d93e49f33b89ac1, and bfacf300a44362d94803036dd1b69ee495dbe605b60615e8fdef364dcaef4f26. The corresponding work-packet IDs are 9abb4edb19c46867a777b68d49562f0469b6fede670c8ca6c3aefdc6b1c6cbe7, d5ed93ba724a2be1ba0d75fe8c5f79377419d040284131519e8eb72d436ed91f, a51fdab21ad6d2bb1bb84a3647d2737a2fc33555371a66afb1e3fa3ae7ad38f8, and 0b85f72190f144b8cd43cb693c9cb97dd1e73b855700adf17226f831b158742d.

The fourth CAS evaluation records bayesian_acquisition, and its persisted fit basis is 7efba6fc9751c9e355860db8ebe91366802eb08812576a72dec1a2dc679cc9e8@ea9961665de593b65e4e6271ea73d96ae868080d5978bb2622a3440abccf9116. Its basis records training_observation_count=3 and the exact first three full evaluation refs above. The old test stopped before reaching its fit-basis assertions; R13 leaves those assertions unchanged so the rerun will exercise them.

## Property correction

The estimator’s clipping law is p' = min(max(p, c), 1-c). For the three selected thresholds below the observed [.375,.4375] support, that operation is inactive: the persisted clipping fraction is zero and repeated ATEs are expected for this fixed source, seed, and estimator. At .450824 every propensity is raised to the lower bound; the actual clipping fraction is 1 and the measured ATE changes. The divergent case for the former gate is therefore concrete: four distinct valid selected method inputs, with three thresholds inactive on the realized support, cannot imply four unique outputs.

The R13 test checks the property from the real path. For each fresh-read MethodResult it validates the persisted propensity support and clipping fraction against the selected threshold, verifies four unique selected values and four unique full MethodResult refs, preserves four unique evaluation refs, and keeps the 40-row/40-draw/packet/profile/request checks. It requires at least two unclipped rows to share the measured ATE plateau, and requires an actively clipped row to differ from that plateau. It retains the existing acquired-fourth-row and exact-three-prior-evaluation fit-basis assertions and the packet-tampering rejection.

This is a P38 correction to an over-specific outcome-uniqueness proxy. It stays within the same configured producer → MethodJob → CAS → fresh-reader property class (P29/P40); it is not a reason to weaken source binding, output checks, currentness, or authority. No “all distinct parameters must change all metrics” rule is added.

## Boundary and disposition

The fixture is synthetic and all four evaluations are non-promotable. The witness demonstrates mechanics for a declared configured profile; it establishes no causal truth, identification, calibration, fiscal-source rule, historical issuer custody, external source authority, or promotion eligibility. B108 remains limited. B157 remains held for its original same-request native L3/L4 and default policy-runtime consumer requirements; this configured Search × MethodJob witness does not close either.

No production source or public contract changes are included. R13 only revises the semantic test oracle and the package/release documentation. Tests, native fits, and the full wave remain unrun against this candidate. formal_closure_ids is empty.
