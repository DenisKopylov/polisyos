# Retire only measured non-regression exceptions

Author proposal on the current candidate, based on slice HEAD `4699fdf8419dd2c89609f68a3edf5f3bfb7c851a`; not a formal G closure.

The complete ratchet report enumerated 13 packages / 2,400 production Python modules. Actual tests were added for distinct source-owned behavior; the mirror metric itself remains a filename/path measure and does not prove capability. The full input report is retained at `LOCAL/dx0-native/raw/current-source-budget-20261010/test-ratchets-final.json`; its exact hash and before/after contract hashes are recorded in `LOCAL/raw/green-ratchet-exception-retirement/retirement-input.json`.

Removed the stale Fabric loose, Foundry loose/strict, and Scientist strict regression exception fields because their current recomputed loose and strict ratios meet the unchanged floor/baseline. No dates, floors, modes or baselines were changed. Runtime still has a loose-floor regression, so its exception was retained pending its issuer/metric choice. The shared-helper count regression is also retained.

| Package | Actual loose ratio | Unchanged floor | Strict status | Raised-floor control | Corrupt-strict-baseline control |
| --- | --- | --- | --- | --- | --- |
| fabric | 0.5058 | 0.502 | no_regression | floor_regression | strict_regression |
| foundry | 0.7178 | 0.7176 | no_regression | floor_regression | strict_regression |
| scientist | 0.7171 | 0.7099 | no_regression | floor_regression | strict_regression |

The controls call the real `_build_package_report` over each actual source/test tree. Only the in-memory floor or strict baseline is changed; both controls produce the real rejection status after retirement. Full deciding output is `LOCAL/raw/green-ratchet-exception-retirement/deciding-controls.json` @ SHA-256 `92542aa36a709d5f9d57353cfdbd888416e7bf88a22c111dd19d106fd01eae48`.

Final composed ratchet replay remains required after the complete source freeze, including any later source denominator changes. See `LOCAL/decisions/hyg04-and-helper-budget-current.md` for the runtime cross-module mapping and helper-budget alternatives.
