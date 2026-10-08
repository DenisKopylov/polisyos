# Prompt-pack review: local data and authority

**Verdict: GO for commissioning; no safety/authority blocker found.** Reviewed the current untracked prompt pack at G snapshot `fe5ccf9ce90c336fff749da48bd0138d321baf23`. This was a document-only read. No tracked/source/ref writes, tests, environment setup, data traversal, or child agents.

## Required boundary checks

- **L01 remains intake, not authority.** It limits discovery to existing configuration/receipts and forbids payload census; it separates internal owner, externally supplied fact, our admission, and claim reaction. It routes existing issuer/verifier code/API discovery to C13 and explicitly says not to invent external permission. Code/API existence alone does not establish a valid issuer for a protected effect.
- **L02 is criterion-scoped.** It runs exact G-admitted candidates with read-only L01 inputs, only where the original criterion requires an authentic source/history/evaluator; it keeps raw rows out of Git and leaves synthetic cloud evidence bounded. Missing input does not stop generic refusal/mechanics.
- **No mount is guessed.** README §“Предел распараллеливания” and `dispatch.json#/actual_local_data_paths` call mounts/recipes `not_established`; L01 resolves local aliases from existing configuration/receipts. No absolute production path is asserted.
- **No blanket production-data gate.** COMMON says unavailable facts constrain a positive, not other ready work; L02 permits an affected narrow check on an exact candidate before the whole E02 freeze, and reserves one consolidated data-dependent closeout for final freeze. Cloud generic checks continue.
- **The latest A/C placement override is explicit.** COMMON states that this user’s cloud/compute choice permits A/C fixture-based authoring in cloud and overrides the older HANDOFF default location while preserving logical canonical owners. C10’s served fixtures and C12’s Legal fixtures are cloud; authentic inputs remain L01/L02 local. The A/C shared writer leases remain singular; G alone publishes integration.
- **Internal vs external authority is correctly split.** D164 asks for an existing issuer/verifier/writer fact first; C11 keeps positive permit work contingent on actual issuer/verifier and requires fake/stale/revoked zero-effect controls. External evidence is needed only when another institution owns the act. No new sovereign permission service or blanket external approval is asked for.

## Non-blocking wording clarification

README line 26 places “L02 authentic local checks” after source freeze, while L02 §“Параллельность и зависимости” allows a narrow affected check before the full freeze; ORCH prompts describe the single final L02 closeout after freeze. Readers can reconcile this as early candidate-bound narrow checks plus one final consolidated closeout, but the README should say that explicitly to avoid delaying a useful narrow check or repeating it. This does not block commissioning because L02 and COMMON specify the candidate and dependency gates.

L01’s “source/ref/input digest” packet is qualified as non-secret; before it leaves local, use an opaque alias and only custodian-approved digest. The pack’s read-only and no-upload rules already prevent payload transfer; this is a precision recommendation, not a blocker.

## Evidence locators

- `README.md:5–7,19,23–26,67–75`: cloud/local split, sequencing, unresolved mount/profile status.
- `COMMON.md:13–17,21–26,30–36`: missing-input non-blocking rule, A/C cloud fixture override, no payload upload, exact-candidate verification.
- `L01.md:9–15`: read-only inventory, plane decomposition, internal issuer/API lookup via C13, no invented permission.
- `L02.md:9,15,19–25`: exact local consumers, criterion scope, read-only inputs and candidate-bound narrow check.
- `ORCH01–04.md:14–20`; `ORCH04.md:23`: one writer lease, route missing facts to L01, generic work continues, G-only integration.
- `C10.md:9,19`, `C12.md:15,19`, `C11.md:15,19`: A/C fixture authoring in cloud, authentic assets local, actual D permit evidence.

Current file hashes:
- README `f353a465fe5c3502cdf750776cf94fc628f88cd5c49af8bf407343c7454263b7`
- COMMON `43d6451fef501f174f3b250f93c0fd7923a42d372aa3b6c1e7f99ff291d8e9ea`
- L01 `5182f6f5efa8f86fb025a7f36ca4cf8c400c551459907a0c41ac4332869aae0e`
- L02 `dfb9525e9ae980d2557c50a237e0aae64445321f094582561f7bd20c8199aab0`
- ORCH01–04 `7666255d98a9bc2b37ff703f3f2336f2c4967eacbf9ad7694af19f3472e14d61`, `dec2371f9b850408b07e99fa9a9ee9373e948df50b82ef1c2f22124c068d92bd`, `db62e5a442db6f9e77960b06a1cc6471c52b7812eb9c7568460c589d060af7ea`, `cfaf7000661146bdf267d6ce37e46c2301d0c643714183dd21a3b855c6288b44`.
