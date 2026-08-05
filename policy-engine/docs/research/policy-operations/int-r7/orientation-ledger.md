---
title: INT-R7 — Orientation Audit Ledger
research_id: INT-R7
status: delivered
result_standing: GO_WITH_REVISIONS
repository: https://github.com/DenisKopylov/polisyos
repository_branch_inspected: main
pinned_repository_commit: 02c5b8d23c757c92b9231e6e1e802d5701588908
inspection_date: 2026-08-04
inspection_method: connected GitHub exact-ref reads and complete pinned-ref code searches; local clone unavailable because the execution environment denied GitHub DNS/egress
research_only: true
int_r8_seam: proof_only
may_not_use_for:
  - production implementation authorization
  - final wire, schema, package, database, serialization, or API contract
  - canonical owner appointment
  - authority grant
  - capability claim
  - benchmark passage
  - legal compliance or institutional competence conclusion
  - permission to publish a governed result
  - automatic amendment of any plan or system-design decision
---

# INT-R7 orientation audit ledger

## 1. Method and result vocabulary

This is Pass I of INT-R7. It audits the supplied repository orientation before any of it is used as a design premise. Every repository observation is pinned to `02c5b8d23c757c92b9231e6e1e802d5701588908`; `path:line @ 02c5b8d` locators are therefore historical locators, not claims about a later `main`.

The requested local clone could not be completed because the execution environment denied outbound GitHub DNS/egress. The connected GitHub integration did permit exact-ref file reads, complete code searches, branch creation and writes. That is a method deviation and is recorded rather than concealed. Where an exact lexical count could not be reproduced with an independently retained tree-walk script, the result is `not_established`; the semantic conclusion is assessed separately.

Result vocabulary:

- `confirmed` — independently established at the pinned object;
- `confirmed_with_narrowing` — correct only after the stated scope is narrowed;
- `corrected` — false as supplied and replaced by a pinned result;
- `not_established` — evidence available in this environment does not justify the exact assertion;
- `not_applicable` — architectural interpretation, not a repository fact.

## 2. Orientation ledger

| ID | Supplied assertion | Result | Pinned evidence, denominator, and correction |
| --- | --- | --- | --- |
| O-01 | `core/artifacts/signing.py` is a 768-line Ed25519 signing module with `KeyPair`, key IDs, detached signatures, canonical statement bytes, a `REVOKED` verification state, revoked-key directory and bulk reports. | **confirmed** | `policy-engine/src/polisyos/core/artifacts/signing.py:1-210, 210-520, 520-768 @ 02c5b8d`. The file declares `SIGNATURE_ALGORITHM = "Ed25519"`, key/signature models, canonical statement bytes, detached signing, directory-based trust/revocation, and bulk reports. |
| O-02 | A full-file lifecycle-vocabulary census is zero for every supplied term. | **not_established for the exact zero table; semantic conclusion confirmed** | Exact-ref inspection found no key-validity interval, certificate path, trusted timestamp, transparency receipt, archival renewal, common-view proof, or historical/current authority split. The exact wildcard-token count must be re-run from a local checkout using §5.2 before it is quoted numerically. |
| O-03 | `core/security/rotation.py` implements rotation for the wrong asset class. | **confirmed** | `policy-engine/src/polisyos/core/security/rotation.py:1-237 @ 02c5b8d` self-describes runtime security rotation, updates a JWT trust-anchor manifest, and manages local Ed25519 key/trust/revocation files. It has active/next/retired/revoked sets but no public-record credential, trusted-time, log, archival-renewal, succession, or record-currentness proof. |
| O-04 | `core/audit/verifier.py` and `standalone_verifier_template.py` are the closest existing offline verifier assets. | **confirmed_with_narrowing** | `policy-engine/src/polisyos/core/audit/verifier.py:1-260, 300-700 @ 02c5b8d`; `policy-engine/src/polisyos/core/audit/standalone_verifier_template.py:1-559 @ 02c5b8d`. They provide package/hash/provenance/dependency and detached-signature verification substrates, but not independently authenticated public trust, signing-time revocation, GY-N12 currentness, transparency witnesses, or archival renewal. |
| O-05 | Exactly 14 production Python modules import/use cryptography, JWT, or HMAC, and the supplied list is complete. | **confirmed; denominator 14/14** | Complete connected search over `policy-engine/src/polisyos/**/*.py`, followed by false-positive inspection, returned the 14 paths in §3. Local symbol/name matches in HTTP files were excluded when they were not imports of the named libraries. |
| O-06 | `core/security/slsa/fulcio.py` is an existing supply-chain identity path. | **confirmed** | `policy-engine/src/polisyos/core/security/slsa/fulcio.py:1-400 @ 02c5b8d` obtains OIDC identity material, creates an ephemeral P-256 key, requests a short-lived Fulcio-style certificate, and supports a local mode. This is a transferable issuance pattern, not public authority or 30-year preservation. |
| O-07 | `runtime/quality/public_export.py` is a real 2,103-line producer and is not signed. | **confirmed** | `policy-engine/src/polisyos/runtime/quality/public_export.py:1-850, 1400-2103 @ 02c5b8d` constructs a redacted projection-only bundle and returns it without a call to the signing owner, a trusted timestamp, certificate/status proof, transparency receipt, or verification result. |
| O-08 | Its full-file `sign`-family census has exactly 36 incidental hits. | **not_established for the exact number; absence of proof integration confirmed** | Exact-ref inspection found no `Ed25519Signer` integration, detached signature, certificate/timestamp/log evidence, or public verifier gate. The lexical number `36` is not repeated as an established fact without a retained local census. |
| O-09 | `build_public_export_bundle` occurs in exactly two Python files: its definition and `runtime/quality/__init__.py`. | **corrected** | Whole-pinned-tree function search found call/definition expressions in five Python files: the definition; `tools/ops_runners/runtime/canary_evidence.py`; `tools/quality/validation/check_layer3_workflow_failure_authority.py`; `tests/unit/runtime/quality/test_multi_tenant_shared_cas.py`; and `tests/unit/runtime/quality/test_public_export.py`. `runtime/quality/__init__.py` is a re-export, not a call. The narrower production result is confirmed: no production `policy-engine/src/polisyos/**/*.py` caller outside the defining module and no HTTP route. Classification remains `bridge_missing`, not `producer_missing`. |
| O-10 | The current dashboard “verification” is a public-salt 32-bit FNV value recomputed in the browser. | **confirmed** | Salt: `policy-engine/apps/runtime-dashboard/src/features/runs/domain/publicationPacket.ts:240-247 @ 02c5b8d`; 32-bit FNV-1a: `:357-369`; packet token and browser verification: `:1050-1188`; positive badge consumption: `PublicDecisionViewerPage.tsx:1-53`. |
| O-11 | Atlas calls the predecessor forgeable and requires DS12 to strangle it. | **confirmed as plan obligation, not capability** | Publication reconstruction row: `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:197-218 @ 02c5b8d`; DS12 gate, real chain requirement, and forged-packet negative control: `:1194-1250`. |
| O-12 | DS12 consumes INT-R7 and INT-R8 before the first public record; DS13 owns later accountability/transparency surfaces. | **confirmed as named plan ownership** | DS12: `POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md:1194-1250`; DS13: `:1293-1310 @ 02c5b8d`. INT-R7 may require minimum common-view/status evidence for DS12 but does not pull all DS13 product work forward. |
| O-13 | `stage0-custody-kernel-ratification.md` is binding and includes append-only correction, authority bands, and `S0-K16`. | **confirmed** | `policy-engine/docs/system-design-decisions/stage0-custody-kernel-ratification.md:1-264 @ 02c5b8d`; relied-on findings are cited by IDs `S0-K08` and `S0-K16`, not by adjacent prose. |
| O-14 | `int-wave-claim-semantics-ratification.md` is binding and changes the signed-claim target. | **confirmed** | `policy-engine/docs/system-design-decisions/int-wave-claim-semantics-ratification.md:1-379 @ 02c5b8d`; relied-on findings: `INT-K01`, `INT-K02`, `INT-K06`, `INT-K08`. The first likely public proof is a falsifiable procedural custody claim carrying no probability; a later `delta` claim must bind its declared obligation set and maintained assumptions. |
| O-15 | GY-N12 is the canonical epoch/currentness seam and must not be duplicated. | **confirmed as canonical plan/research ownership** | The GY-N12 material defines epoch identity, stale/revalidation semantics, append-only reissue and OpenWorldRisk behavior. INT-R7 consumes those results in its proof predicates; it does not create an epoch manager or new lattice. |
| O-16 | P35 and P36 bind the method. | **confirmed** | `policy-engine/docs/reference/policy-design-case-failure-patterns.md:83-135 @ 02c5b8d`: P35 requires complete-set enumeration with a denominator; P36 requires a finding ID and recomputation from the pinned owner rather than authority by adjacent prose. |
| O-17 | OPS-R14 is active and undelivered, so INT-R7 must declare resilience dependencies rather than invent DR/archive mechanics. | **confirmed** | `policy-engine/docs/research/policy-operations-and-real-world-runtime-backlog.md:400-510 @ 02c5b8d` assigns custody-grade resilience, expiring authority, long-term signed-record replay and legal-hold override to OPS-R14. |

## 3. Complete production cryptography/JWT/HMAC path census

Boundary: every Python file under `policy-engine/src/polisyos/` at the pinned commit. Inclusion rule: actual import rooted at `cryptography`, `jwt`, or `hmac`, or confirmed module-qualified use. Denominator: **14 included paths / 14 total included paths**.

1. `core/artifacts/signing.py`
2. `core/audit/_assembler_core.py`
3. `core/audit/_assembler_provenance.py`
4. `core/audit/standalone_verifier_template.py`
5. `core/audit/verifier.py`
6. `core/security/delegation.py`
7. `core/security/identity.py`
8. `core/security/slsa/fulcio.py`
9. `data_forge/domains/catalog/knowledge/acquisition_authority.py`
10. `fabric/connectors/cache/_store_serialization.py`
11. `runtime/http/csrf.py`
12. `runtime/http/deployment_security.py`
13. `runtime/http/services/export_replay.py`
14. `runtime/http/step_up.py`

This census identifies primitive use only. It does not imply public-verification capability or authority by adjacency.

## 4. Additional high-consequence findings

### O-F01 — signing time and identity are mutable metadata

`DetachedSignature.signed_at` and `signer_identity` are outside `SignatureStatement`; `canonical_statement_bytes()` serializes only the statement and the signature covers those bytes. Editing the displayed time or identity hint therefore need not invalidate the Ed25519 signature. Evidence: `signing.py:53-94, 291-302, 389-411, 539-683 @ 02c5b8d`.

Consequence: the current sidecar cannot establish “signed before revocation” or institutional identity-at-time. Trusted time and authenticated authority history are separate predicates.

### O-F02 — local revocation is timeless

The verifier checks whether `key_id` is in a local revoked-key set before signature verification, with no effective time, compromise interval, reason, certificate status evidence, or signing-time proof. Evidence: `signing.py:469-517, 583-610 @ 02c5b8d`.

Consequence: it conflates historically authentic issuance with present trust. INT-R7 requires `HistoricalAuthenticity` and `CurrentAuthority` to remain distinct.

### O-F03 — portable package trust is package-relative unless externally anchored

The standalone substrate can load public keys shipped with the package. An attacker replacing payload, signature and bundled key together can satisfy package-relative integrity unless the key/trust snapshot is authenticated independently. Evidence: `standalone_verifier_template.py:1-559` and `core/audit/verifier.py:300-700 @ 02c5b8d`.

Consequence: reuse the execution substrate, not the trust shortcut.

### O-F04 — FNV forgery is constructive

The salt and function are public and the attacker chooses the JSON. No collision search is required: compute the eight-hex-character value for the replacement payload and construct a URL the browser accepts. Evidence: `publicationPacket.ts:240-247, 357-369, 1050-1188 @ 02c5b8d`.

Consequence: the legacy mechanism must be incapable of any positive authority label; a warning next to `Verified` is not a strangle.

## 5. Reproduction recipes

### 5.1 Baseline

```bash
git clone https://github.com/DenisKopylov/polisyos.git
cd polisyos
git checkout --detach 02c5b8d23c757c92b9231e6e1e802d5701588908
test "$(git rev-parse HEAD)" = "02c5b8d23c757c92b9231e6e1e802d5701588908"
```

### 5.2 Signing-module vocabulary

```python
from pathlib import Path
import re

text = Path("policy-engine/src/polisyos/core/artifacts/signing.py").read_text(encoding="utf-8").casefold()
patterns = {
    "rotat*": r"\brotat\w*", "transparen*": r"\btransparen\w*",
    "equivocat*": r"\bequivocat\w*", "split view": r"split[ _-]view",
    "archiv*": r"\barchiv\w*", "algorithm_agility": r"algorithm[_ -]agility",
    "offline": r"\boffline\b", "expiry": r"\bexpiry\b",
    "not_after": r"\bnot_after\b", "valid_until": r"\bvalid_until\b",
    "chain": r"\bchain\b", "trust_root": r"\btrust_root\b",
    "anchor": r"\banchor\b", "countersign": r"\bcountersign\w*",
    "timestamp": r"\btimestamp\w*",
}
for label, pattern in patterns.items():
    print(label, len(re.findall(pattern, text)))
```

### 5.3 Public-export calls versus re-exports

```python
from pathlib import Path
import ast

root = Path("policy-engine")
target = "build_public_export_bundle"
rows = []
for path in sorted(root.rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
            rows.append((str(path), node.lineno, "definition"))
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name == target:
                rows.append((str(path), node.lineno, "call"))
for row in rows:
    print(*row, sep="\t")
print("denominator", len(rows))
```

### 5.4 Crypto import denominator

```python
from pathlib import Path
import ast

root = Path("policy-engine/src/polisyos")
roots = {"cryptography", "jwt", "hmac"}
paths = []
for path in sorted(root.rglob("*.py")):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    matched = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            matched |= any(a.name.split(".")[0] in roots for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            matched |= node.module.split(".")[0] in roots
    if matched:
        paths.append(path.relative_to(root).as_posix())
print("denominator", len(paths))
print("\n".join(paths))
```

## 6. Pass-I disposition

The orientation is usable after one material correction and two exact-count reservations:

1. the claimed whole-tree caller count for `build_public_export_bundle` was false; production HTTP bridge absence remains true;
2. the exact zero vocabulary table in `signing.py` must be locally reproduced before numerical reuse;
3. the exact `36` sign-family count in `public_export.py` must likewise be locally reproduced; unsigned proof integration is independently established.

The capability conclusion is unchanged and narrowly stated at the pinned commit:

- signing primitive: present;
- operator/runtime rotation: present;
- portable package-verification substrate: present;
- redacted public projection producer: present;
- public proof lifecycle, temporal revocation, common-view proof, archival renewal, production publication bridge and citizen-grade verification semantics: absent or missing at the classified links.

This is research evidence only, not a capability claim about a later revision and not authorization to publish.
