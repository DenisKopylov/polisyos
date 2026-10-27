# C08 cloud receipt — e02-c08-20261027-r1

## Identity and environment

- Task environment: `polisyos` (`6965429cdb308191a0e6eb63cb118ea3`); branch observation: attached `work`.
- Base: commit `8db01b1076e425b7998b05a658776c991b7bd594`, tree `1706923ebe943f1a332dca4860cd145ddd366e36`.
- Architecture-selection object `14bf638032063c3d5a92b29da4215b3b54951fd6` was unavailable; implementation used the prompt's inline selected law.
- Initial capacity: disk 32G total / 28G available; 2,097,152 total / 1,984,596 free inodes; RAM 17Gi total / 16Gi available; no swap. Python 3.14.4, uv 0.7.22, Node 24.15.0, pnpm 10.28.1.

## Delivered classification and footprint

Class A source implements exact-version `0.3.0` ordinary `_type` mapping escaping in the neutral codec and owner-selected Core/IR byte readers. Class A tests cover raw known/future/null/non-string tags, nested and escape-shaped mappings, native/raw distinction, malformed wrappers, duplicate names, exact `.2` default behavior, and distinct Core/IR exception/tag policies.

Changed paths are the paths reported by `git diff --name-only 8db01b1076e425b7998b05a658776c991b7bd594` in the delivered commit. The public-surface inventory and generated reference are excluded shared generated families and were not changed. Companion proposal: the later root-selected writer should run the repository public-surface generator/check against this commit after deciding whether the additive `version` reader selector is public-stable or public-experimental.

## Outcomes

- PASS — focused codec suite: 43 tests passed.
- PASS — `git diff --check`.
- ERROR (environment) — lint extra provisioning could not download `librt==0.7.7` through the network tunnel; the existing environment does not contain Ruff.
- UNRUN — broad consumer/Foundry/scientist/package proof, per the task's instruction to defer the expensive frozen wave.
- UNRUN / dependency result — physical pre-effect writer admission is not claimed by this bounded delivery. Existing `CoreJsonReadLimits` and bounded CAS manifest/member owners cover reader I/O, but no selected source owner currently supplies a writer-side immutable resource vector before Pydantic `model_dump`, callback, or Decimal projection. Enabling `.3` writer cohorts therefore remains disabled. The next source slice must add that typed writer admission owner and exercise model/callback/Decimal spies before any cohort switch; silently applying read limits after projection would not satisfy the selected law.

## Commands

```text
git rev-parse HEAD HEAD^{tree}; git branch --show-current; git status --short --branch
df -h .; df -i .; free -h; python --version; uv --version; node --version; corepack pnpm --version
uv run --frozen --extra test pytest -q tests/unit/common/test_canonical.py tests/unit/common/test_canonical_v3.py tests/unit/core/phase0/test_canon_json.py tests/unit/core/canon/test_core_canon_v3.py tests/unit/ir/test_canon_hardening.py tests/unit/ir/test_canon_v3.py
git diff --check
uv run --frozen --extra lint python -m ruff check <changed Python paths>
.venv/bin/python -m ruff check <changed Python paths>
```

Final commit/tree and exact changed-footprint hashes are recorded by Git; this receipt intentionally avoids a self-referential future receipt hash. Independent review and G acceptance remain pending; this is not formal LA-021 closure.
