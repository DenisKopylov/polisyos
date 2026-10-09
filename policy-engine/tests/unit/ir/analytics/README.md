# IR Analytics Unit Tests

This subtree covers analytics contracts, projections, and cross-package
analytics adapters for IR.

`test_posterior_summary.py` verifies v1.1 posterior mean/median separation from equal-tail bounds,
retains exact producer draw rows and content bindings, refuses mismatched chain/draw axes, and
rejects source-declared weights that this profile does not interpret.
