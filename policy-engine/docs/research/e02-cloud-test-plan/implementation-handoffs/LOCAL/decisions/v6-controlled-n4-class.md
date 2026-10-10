# V6 controlled N4 port class repair proposal

P40 classification: SAME_CLASS_DEEPER within the root-producer → actual child execution → persisted sibling witness. The V6 rewrite left both successful-child branches constructing `_ControlledN4GenerationPort` while removing its nested definition. Restore the shared runtime wrapper once before branch selection so both the ordinary selected child and the successful sibling call the actual `N4GenerationPort` and record the proposal in `n4_organ_runs`; preserve the dedicated failed-sibling port and all existing child/context/source assertions. This repairs the helper's operability as a whole, not a one-branch example.

The patch reintroduces the original nested wrapper body only. It adds no profile, authority, causal, currentness, or publication claim.

Patch footprint: `policy-engine/tests/unit/runtime/http/test_control_service_di.py` only.

Base test-source SHA-256: `c76c5aa4508057a6fe95909f040cca3e11ff7aa6389f60502891045d56cafcc5`. Unchanged producer source `policy-engine/src/polisyos/runtime/http/services/control/generation_cycle.py` SHA-256: `c4492d44e17df4c18364bf1e23aee3dd9c346d3a12f3b689e341e86c288f35c9`.

Patch SHA-256: `8fb51af8f45b0051833a2101ef44f6e6c3dbe2d2727ae863669157761be14e78`

The patch is unapplied. No tests or Git commands were run.
