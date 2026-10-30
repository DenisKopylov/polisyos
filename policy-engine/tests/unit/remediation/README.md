# Remediation behavior tests

This directory holds focused regression and semantic tests for named remediation
criteria. Test filenames identify the affected criterion; inspect the corresponding
owner, source and current criterion before treating a test as complete evidence.

Run the directory from `policy-engine/` with `uv run pytest tests/unit/remediation -q`.
This selection does not replace affected integration, installed-package or production
verification where a criterion requires those surfaces.
