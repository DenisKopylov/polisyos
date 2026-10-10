# K3 replica-failure projection patch candidate

Base: `13e411da7d9e505856fc336b3d25fd0aabdb1f66` (tree `8d8c4082febf1676dd86084106f3266d8b2131a3`).

Patch artifact: `LOCAL/raw/k3-failure-projection-patch-13e411da.patch`
SHA-256: `01ae1c7e35f1b216d6ac76d90062f0f8b33883cb35d43f813bb8b7fdc53f7b25`

This is a patch-only proposal. It changes no source checkout files and was not applied or test-run. The production change resolves one failed replica's displayed failure once: retain a concrete adapter cause first, otherwise use the persisted workflow node error's actual code/message, and only then retain the existing caught/status fallback. The workflow status and structured `workflow_failures` remain intact. The same resolved cause feeds both cohort `failure` and warning projection.

The integration controls distinguish two real paths: the middle replica's injected `RuntimeError` at the Foundry adapter boundary, and the existing real `bind_foundry_inputs` failure before any Foundry request, whose persisted workflow report is the only concrete cause. Existing cohort counts, seed order, survivor artifacts, and fresh CAS report/cohort reads stay asserted. The projection-only report assertion now checks the exact scenario-qualified degraded reason observed in the durable report.

P40: SAME_CLASS_DEEPER (replica failure projection). The patch widens the shared projection boundary; it adds no cause-specific message recognition or per-replica exception mapping. It does not claim new workflow status or evidence authority.

Source witnesses from the frozen K3 run: `LOCAL/raw/composed-mac-current-source-20261010/k3_foundry_replicas_seeds_31_32_33/{junit.xml,stdout.bin,metadata.json}`. Existing bundle status is retained; this patch has not been applied, reviewed, or verified by rerunning tests.
