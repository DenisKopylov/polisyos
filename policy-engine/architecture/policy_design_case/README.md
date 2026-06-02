# Policy Design Case Architecture Records

This directory owns the committed Policy Design Case control-plane records used
by Layer 2 readiness gates, cluster ownership checks, capability inventories,
and slice manifests.

The files here are authority-bearing repository artifacts, not local scratch
state. Update them only when a slice closure or governance validator changes
the corresponding contract, and keep the validator or manifest reference in
sync with `architecture/policy_design_case/inventory.json`.
