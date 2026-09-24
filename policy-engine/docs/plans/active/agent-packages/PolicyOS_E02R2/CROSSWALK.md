# E02-R2 finding crosswalk to live plans and register rows

## Census and rule

The input census covers all 282 findings (225 B + 57 LA) against the complete 127-entry E02 bundle catalog: 35,814 possible finding/bundle cells, with 291 declared membership edges across 282 findings and 127 unique bundles. Eight findings require more than one bundle. Each row below carries its complete declared bundle set; absent matrix cells mean “not declared,” not a semantic conclusion.

A plan/register relation is admitted only when an exact finding-to-bundle mapping leads to a bundle/record owner span that names the same production owner or scope in a specific live GY task or Atlas slice, or when a reviewed row-level triage explicitly names the relation. A whole-document path-string hit, nearby narrative, or shared domain noun is insufficient. `touches code named by` states owner-scope overlap only; `advances` and `conflicts` retain their literal meaning. No relation here claims task completion or register closure.

Inputs: bundle catalog `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/bundle_manifest.json@git-blob:130ba865f6df9b1e7cd3bec5ce868df85e9b918c`; B mapping `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/finding_to_bundle.json@git-blob:a6d76fefcca9519962e50684d4377d4eec2aa12c`; LA mapping `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02_Combined_Agent_Package/legacy_to_bundles.json@git-blob:329f101acca8dac6708b4e557cd07fd58f5facb7`; GY plan `policy-engine/docs/plans/active/layer3-slices/GY-engine-subordination.md@git-blob:9d510e2ee43fd017028542f180008cd2c2aacb37`; Atlas master `policy-engine/docs/plans/active/POLICYOS_ATLAS_SURFACE_IMPLEMENTATION_MASTER_PLAN.md@git-blob:21002cfb2805f718ef7e906e8df1c4ecb30c015d`. The reviewed partial triage, held audit, and bundle/task owner spans are cited for each admitted edge below.

## Discrepancies first

- The prior draft’s 79/282 linked and 203/282 unmatched counts are withdrawn. It used normalized whole-document path joins, which admitted false targets such as GY-DEF12 and an incidental LA-021 → GY-AS1 import-policy overlap.
- No DEBT-register row relation is asserted from path coincidence. An exact B/LA-identifier search in the current DEBT-REGISTER.md and LEDGER.md returns no matches; that absence does not prove no dependency, so all unlinked finding/register pairs remain `not_established` until an exact owner-span mapping is supplied.
- LA-021 has no live-plan edge from the architecture import-policy file. Its bounded closure evidence is the CAN-01 parity re-check in the residual ledger; that does not itself close a GY or Atlas task.
- B01–B03 do not receive a plan edge from general CYC-01 wording. R1 can use the existing hash-verified compiled-run/context references and owner resolver; N4 initial context is verified, but N7 re-entry lacks an owner-issued post-growth context. That S8 authority predicate remains `not_established` pending a canonical post-growth witness, potentially through R13, while ordinary candidate computation proceeds with a typed limitation.

## Supported direct relations

| Finding ID | Bundle declaration | Target | Relation | Exact basis and limit |
|---|---|---|---|---|
| B12 | ACQ-01 | GY-N13b; Atlas DS15 | conflicts | PARTIAL_TRIAGE.md@git-blob:b07ccbc1e3b587efd1cae483c6eb18fecb25c81f#B12; ACQ-01/N13b and DS15 owner scope; R13 requires the served bridge and admission/passport/epoch chain; production producer remains missing. |
| LA-046 | REQ-01, ACQ-01 | GY-N13b; Atlas DS15 | conflicts | PARTIAL_TRIAGE.md@git-blob:b07ccbc1e3b587efd1cae483c6eb18fecb25c81f#LA-046; ACQ-01/N13b and DS15 owner scope; same ACQ-01 production-route conflict, preserving the typed producer-missing boundary. |
| B13 | RES-03 | GY-PR1 | advances | PARTIAL_TRIAGE.md@git-blob:b07ccbc1e3b587efd1cae483c6eb18fecb25c81f#B13; row-level typed candidate-only advancement; the typed candidate-only limitation advances sequencing and does not create authority. |
| B19, B21, B23, B26 | SIM-03 | GY-N5 | touches code named by | bundles/SIM-03.md@git-blob:3cdd86c9e9cabe23dbaf4b9f9770fbffabd889cb; GY-engine-subordination.md@git-blob:9d510e2ee43fd017028542f180008cd2c2aacb37#GY-N5 (joint-simulation horizon); joint_simulation_horizon.py@git-blob:e74fa941d673b98b51e3b90934db666ecfa6467c; direct joint-simulation owner path only; no ParetoPromoter or Atlas DS12/DS13 edge is inferred. |
| B201, B202 | UQS-01 | Atlas DS16 | touches code named by | Held review and the DS16 scope name value/uncertainty grammar and public IR versioning; owner decision remains pending. HELD_REVIEW.md@git-blob:69aaa5293cd33c34f592d5e400592ee9305c7d23#B201; Atlas master@git-blob:21002cfb2805f718ef7e906e8df1c4ecb30c015d#DS16; DS16 slice@git-blob:442a19e8921fd1aed903f136c744be144c7652b2 |

Supported set: 9 unique finding IDs, 11 finding-to-target edges. The direct-relation set is intentionally narrow; every omitted target remains `not_established`, not disproved.

## Complete finding-to-bundle declaration crosswalk

| Finding | Complete E02 bundle declaration(s) | Supported plan relation(s) | Otherwise |
|---|---|---|---|
| B01 | CYC-01 | — | not_established: no exact owner-span edge admitted. |
| B02 | CYC-01 | — | not_established: no exact owner-span edge admitted. |
| B03 | CYC-01 | — | not_established: no exact owner-span edge admitted. |
| B04 | CYC-02 | — | not_established: no exact owner-span edge admitted. |
| B05 | CYC-02 | — | not_established: no exact owner-span edge admitted. |
| B06 | SIM-01 | — | not_established: no exact owner-span edge admitted. |
| B07 | SIM-01 | — | not_established: no exact owner-span edge admitted. |
| B08 | CYC-02 | — | not_established: no exact owner-span edge admitted. |
| B09 | CYC-03 | — | not_established: no exact owner-span edge admitted. |
| B10 | CYC-04 | — | not_established: no exact owner-span edge admitted. |
| B11 | CYC-04 | — | not_established: no exact owner-span edge admitted. |
| B12 | ACQ-01 | GY-N13b + Atlas DS15: conflicts | No additional plan/register relation established. |
| B13 | RES-03 | GY-PR1: advances | No additional plan/register relation established. |
| B14 | RUN-01 | — | not_established: no exact owner-span edge admitted. |
| B15 | CYC-05 | — | not_established: no exact owner-span edge admitted. |
| B16 | EMP-01 | — | not_established: no exact owner-span edge admitted. |
| B17 | SCL-01 | — | not_established: no exact owner-span edge admitted. |
| B18 | SIM-02 | — | not_established: no exact owner-span edge admitted. |
| B19 | SIM-03 | GY-N5: touches code named by | No additional plan/register relation established. |
| B20 | SIM-02 | — | not_established: no exact owner-span edge admitted. |
| B21 | SIM-03 | GY-N5: touches code named by | No additional plan/register relation established. |
| B22 | SIM-02 | — | not_established: no exact owner-span edge admitted. |
| B23 | SIM-03 | GY-N5: touches code named by | No additional plan/register relation established. |
| B24 | RUN-02 | — | not_established: no exact owner-span edge admitted. |
| B25 | SIM-03 | — | not_established: no exact owner-span edge admitted. |
| B26 | SIM-03 | GY-N5: touches code named by | No additional plan/register relation established. |
| B27 | CYC-03 | — | not_established: no exact owner-span edge admitted. |
| B28 | CYC-03 | — | not_established: no exact owner-span edge admitted. |
| B29 | CYC-05 | — | not_established: no exact owner-span edge admitted. |
| B30 | CYC-05 | — | not_established: no exact owner-span edge admitted. |
| B31 | EMP-01 | — | not_established: no exact owner-span edge admitted. |
| B32 | FRC-01 | — | not_established: no exact owner-span edge admitted. |
| B33 | EMP-01 | — | not_established: no exact owner-span edge admitted. |
| B34 | SEL-01 | — | not_established: no exact owner-span edge admitted. |
| B35 | SEL-01 | — | not_established: no exact owner-span edge admitted. |
| B36 | SEL-01 | — | not_established: no exact owner-span edge admitted. |
| B37 | DUR-01 | — | not_established: no exact owner-span edge admitted. |
| B38 | DUR-02 | — | not_established: no exact owner-span edge admitted. |
| B39 | RUN-03 | — | not_established: no exact owner-span edge admitted. |
| B40 | RUN-01 | — | not_established: no exact owner-span edge admitted. |
| B41 | STP-01 | — | not_established: no exact owner-span edge admitted. |
| B42 | CMP-01 | — | not_established: no exact owner-span edge admitted. |
| B43 | CMP-01 | — | not_established: no exact owner-span edge admitted. |
| B44 | CMP-01 | — | not_established: no exact owner-span edge admitted. |
| B45 | CMP-02 | — | not_established: no exact owner-span edge admitted. |
| B46 | CMP-02 | — | not_established: no exact owner-span edge admitted. |
| B47 | CMP-03 | — | not_established: no exact owner-span edge admitted. |
| B48 | CMP-03 | — | not_established: no exact owner-span edge admitted. |
| B49 | JIT-01 | — | not_established: no exact owner-span edge admitted. |
| B50 | JIT-01 | — | not_established: no exact owner-span edge admitted. |
| B51 | EXE-01 | — | not_established: no exact owner-span edge admitted. |
| B52 | EXE-01 | — | not_established: no exact owner-span edge admitted. |
| B53 | JIT-01 | — | not_established: no exact owner-span edge admitted. |
| B54 | FIT-01 | — | not_established: no exact owner-span edge admitted. |
| B55 | EXE-01 | — | not_established: no exact owner-span edge admitted. |
| B56 | FIT-01 | — | not_established: no exact owner-span edge admitted. |
| B57 | STA-01 | — | not_established: no exact owner-span edge admitted. |
| B58 | STA-01 | — | not_established: no exact owner-span edge admitted. |
| B59 | STA-01 | — | not_established: no exact owner-span edge admitted. |
| B60 | STA-02 | — | not_established: no exact owner-span edge admitted. |
| B61 | STA-02 | — | not_established: no exact owner-span edge admitted. |
| B62 | STA-02 | — | not_established: no exact owner-span edge admitted. |
| B63 | RES-01 | — | not_established: no exact owner-span edge admitted. |
| B64 | LLM-01 | — | not_established: no exact owner-span edge admitted. |
| B65 | LLM-01 | — | not_established: no exact owner-span edge admitted. |
| B66 | LLM-01 | — | not_established: no exact owner-span edge admitted. |
| B67 | LLM-02 | — | not_established: no exact owner-span edge admitted. |
| B68 | LLM-02 | — | not_established: no exact owner-span edge admitted. |
| B69 | RUN-01 | — | not_established: no exact owner-span edge admitted. |
| B70 | RES-01 | — | not_established: no exact owner-span edge admitted. |
| B71 | RES-01 | — | not_established: no exact owner-span edge admitted. |
| B72 | RES-02 | — | not_established: no exact owner-span edge admitted. |
| B73 | RES-02 | — | not_established: no exact owner-span edge admitted. |
| B74 | RES-04 | — | not_established: no exact owner-span edge admitted. |
| B75 | RES-04 | — | not_established: no exact owner-span edge admitted. |
| B76 | RES-04 | — | not_established: no exact owner-span edge admitted. |
| B77 | EXE-02 | — | not_established: no exact owner-span edge admitted. |
| B78 | DUR-02 | — | not_established: no exact owner-span edge admitted. |
| B79 | ING-01 | — | not_established: no exact owner-span edge admitted. |
| B80 | ING-01 | — | not_established: no exact owner-span edge admitted. |
| B81 | ING-02 | — | not_established: no exact owner-span edge admitted. |
| B82 | ING-02 | — | not_established: no exact owner-span edge admitted. |
| B83 | ING-03 | — | not_established: no exact owner-span edge admitted. |
| B84 | ING-03 | — | not_established: no exact owner-span edge admitted. |
| B85 | ING-02 | — | not_established: no exact owner-span edge admitted. |
| B86 | ING-03 | — | not_established: no exact owner-span edge admitted. |
| B87 | NET-01 | — | not_established: no exact owner-span edge admitted. |
| B88 | ING-01 | — | not_established: no exact owner-span edge admitted. |
| B89 | NET-01 | — | not_established: no exact owner-span edge admitted. |
| B90 | NET-01 | — | not_established: no exact owner-span edge admitted. |
| B91 | NET-02 | — | not_established: no exact owner-span edge admitted. |
| B92 | NET-02 | — | not_established: no exact owner-span edge admitted. |
| B93 | NET-02 | — | not_established: no exact owner-span edge admitted. |
| B94 | WIRE-01 | — | not_established: no exact owner-span edge admitted. |
| B95 | RUN-01 | — | not_established: no exact owner-span edge admitted. |
| B96 | RUN-03 | — | not_established: no exact owner-span edge admitted. |
| B97 | DOE-01 | — | not_established: no exact owner-span edge admitted. |
| B98 | DOE-01 | — | not_established: no exact owner-span edge admitted. |
| B99 | DOE-01 | — | not_established: no exact owner-span edge admitted. |
| B100 | DOE-02 | — | not_established: no exact owner-span edge admitted. |
| B101 | DOE-02 | — | not_established: no exact owner-span edge admitted. |
| B102 | DOE-03 | — | not_established: no exact owner-span edge admitted. |
| B103 | DOE-03 | — | not_established: no exact owner-span edge admitted. |
| B104 | DOE-03 | — | not_established: no exact owner-span edge admitted. |
| B105 | DOE-03 | — | not_established: no exact owner-span edge admitted. |
| B106 | STR-01 | — | not_established: no exact owner-span edge admitted. |
| B107 | STR-01 | — | not_established: no exact owner-span edge admitted. |
| B108 | OPT-01 | — | not_established: no exact owner-span edge admitted. |
| B109 | OPT-01 | — | not_established: no exact owner-span edge admitted. |
| B110 | OPT-01 | — | not_established: no exact owner-span edge admitted. |
| B111 | OPT-01 | — | not_established: no exact owner-span edge admitted. |
| B112 | OPT-02 | — | not_established: no exact owner-span edge admitted. |
| B113 | OPT-02 | — | not_established: no exact owner-span edge admitted. |
| B114 | OPT-03 | — | not_established: no exact owner-span edge admitted. |
| B115 | OPT-03 | — | not_established: no exact owner-span edge admitted. |
| B116 | OPT-04 | — | not_established: no exact owner-span edge admitted. |
| B117 | OPT-04 | — | not_established: no exact owner-span edge admitted. |
| B118 | CTL-01 | — | not_established: no exact owner-span edge admitted. |
| B119 | CTL-01 | — | not_established: no exact owner-span edge admitted. |
| B120 | CTL-03 | — | not_established: no exact owner-span edge admitted. |
| B121 | CTL-03 | — | not_established: no exact owner-span edge admitted. |
| B122 | STP-01 | — | not_established: no exact owner-span edge admitted. |
| B123 | CTL-03 | — | not_established: no exact owner-span edge admitted. |
| B124 | CTL-02 | — | not_established: no exact owner-span edge admitted. |
| B125 | CTL-02 | — | not_established: no exact owner-span edge admitted. |
| B126 | CTL-02 | — | not_established: no exact owner-span edge admitted. |
| B127 | OPT-02 | — | not_established: no exact owner-span edge admitted. |
| B128 | TRN-01 | — | not_established: no exact owner-span edge admitted. |
| B129 | TRN-02 | — | not_established: no exact owner-span edge admitted. |
| B130 | TRN-01 | — | not_established: no exact owner-span edge admitted. |
| B131 | TRN-01 | — | not_established: no exact owner-span edge admitted. |
| B132 | TRN-01 | — | not_established: no exact owner-span edge admitted. |
| B133 | TRN-02 | — | not_established: no exact owner-span edge admitted. |
| B134 | TRN-02 | — | not_established: no exact owner-span edge admitted. |
| B135 | TRN-03 | — | not_established: no exact owner-span edge admitted. |
| B136 | TRN-03 | — | not_established: no exact owner-span edge admitted. |
| B137 | TRN-03 | — | not_established: no exact owner-span edge admitted. |
| B138 | FED-01 | — | not_established: no exact owner-span edge admitted. |
| B139 | FED-02 | — | not_established: no exact owner-span edge admitted. |
| B140 | FED-01 | — | not_established: no exact owner-span edge admitted. |
| B141 | FED-01 | — | not_established: no exact owner-span edge admitted. |
| B142 | FED-02 | — | not_established: no exact owner-span edge admitted. |
| B143 | FED-02 | — | not_established: no exact owner-span edge admitted. |
| B144 | FED-02 | — | not_established: no exact owner-span edge admitted. |
| B145 | FED-01 | — | not_established: no exact owner-span edge admitted. |
| B146 | OBS-01 | — | not_established: no exact owner-span edge admitted. |
| B147 | OBS-02 | — | not_established: no exact owner-span edge admitted. |
| B148 | CAS-02 | — | not_established: no exact owner-span edge admitted. |
| B149 | CAS-02 | — | not_established: no exact owner-span edge admitted. |
| B150 | CAS-01 | — | not_established: no exact owner-span edge admitted. |
| B151 | CAS-01 | — | not_established: no exact owner-span edge admitted. |
| B152 | CAS-03 | — | not_established: no exact owner-span edge admitted. |
| B153 | CAS-01 | — | not_established: no exact owner-span edge admitted. |
| B154 | CAS-03 | — | not_established: no exact owner-span edge admitted. |
| B155 | CAS-03 | — | not_established: no exact owner-span edge admitted. |
| B156 | FUN-01 | — | not_established: no exact owner-span edge admitted. |
| B157 | FUN-02 | — | not_established: no exact owner-span edge admitted. |
| B158 | FUN-01 | — | not_established: no exact owner-span edge admitted. |
| B159 | FUN-01 | — | not_established: no exact owner-span edge admitted. |
| B160 | FUN-02 | — | not_established: no exact owner-span edge admitted. |
| B161 | FUN-03 | — | not_established: no exact owner-span edge admitted. |
| B162 | FUN-02 | — | not_established: no exact owner-span edge admitted. |
| B163 | FUN-03 | — | not_established: no exact owner-span edge admitted. |
| B164 | FUN-03 | — | not_established: no exact owner-span edge admitted. |
| B165 | FUN-02 | — | not_established: no exact owner-span edge admitted. |
| B166 | BKT-01 | — | not_established: no exact owner-span edge admitted. |
| B167 | BKT-02 | — | not_established: no exact owner-span edge admitted. |
| B168 | BKT-02 | — | not_established: no exact owner-span edge admitted. |
| B169 | BKT-01 | — | not_established: no exact owner-span edge admitted. |
| B170 | BKT-01 | — | not_established: no exact owner-span edge admitted. |
| B171 | BKT-02 | — | not_established: no exact owner-span edge admitted. |
| B172 | BKT-03 | — | not_established: no exact owner-span edge admitted. |
| B173 | BKT-03 | — | not_established: no exact owner-span edge admitted. |
| B174 | BKT-04 | — | not_established: no exact owner-span edge admitted. |
| B175 | BKT-04 | — | not_established: no exact owner-span edge admitted. |
| B176 | CAL-01 | — | not_established: no exact owner-span edge admitted. |
| B177 | CAL-01 | — | not_established: no exact owner-span edge admitted. |
| B178 | CAL-01 | — | not_established: no exact owner-span edge admitted. |
| B179 | CAL-02 | — | not_established: no exact owner-span edge admitted. |
| B180 | CAL-02 | — | not_established: no exact owner-span edge admitted. |
| B181 | CAL-02 | — | not_established: no exact owner-span edge admitted. |
| B182 | CAL-02 | — | not_established: no exact owner-span edge admitted. |
| B183 | CAL-03 | — | not_established: no exact owner-span edge admitted. |
| B184 | CAL-04 | — | not_established: no exact owner-span edge admitted. |
| B185 | CAL-05 | — | not_established: no exact owner-span edge admitted. |
| B186 | UQP-01 | — | not_established: no exact owner-span edge admitted. |
| B187 | UQP-02 | — | not_established: no exact owner-span edge admitted. |
| B188 | UQP-02 | — | not_established: no exact owner-span edge admitted. |
| B189 | UQP-01 | — | not_established: no exact owner-span edge admitted. |
| B190 | UQP-01 | — | not_established: no exact owner-span edge admitted. |
| B191 | UQP-01 | — | not_established: no exact owner-span edge admitted. |
| B192 | UQP-02 | — | not_established: no exact owner-span edge admitted. |
| B193 | UQP-03 | — | not_established: no exact owner-span edge admitted. |
| B194 | UQP-03 | — | not_established: no exact owner-span edge admitted. |
| B195 | CAL-03 | — | not_established: no exact owner-span edge admitted. |
| B196 | CAL-04 | — | not_established: no exact owner-span edge admitted. |
| B197 | CAL-06 | — | not_established: no exact owner-span edge admitted. |
| B198 | CAL-06 | — | not_established: no exact owner-span edge admitted. |
| B199 | UQS-01 | — | not_established: no exact owner-span edge admitted. |
| B200 | UQS-01 | — | not_established: no exact owner-span edge admitted. |
| B201 | UQS-01 | Atlas DS16: touches code named by | No additional plan/register relation established. |
| B202 | UQS-01 | Atlas DS16: touches code named by | No additional plan/register relation established. |
| B203 | CAL-04 | — | not_established: no exact owner-span edge admitted. |
| B204 | CAU-01 | — | not_established: no exact owner-span edge admitted. |
| B205 | CAU-01 | — | not_established: no exact owner-span edge admitted. |
| B206 | CAU-01 | — | not_established: no exact owner-span edge admitted. |
| B207 | CAU-02 | — | not_established: no exact owner-span edge admitted. |
| B208 | CAU-02 | — | not_established: no exact owner-span edge admitted. |
| B209 | CAU-02 | — | not_established: no exact owner-span edge admitted. |
| B210 | CAU-03 | — | not_established: no exact owner-span edge admitted. |
| B211 | CAU-03 | — | not_established: no exact owner-span edge admitted. |
| B212 | CAU-04 | — | not_established: no exact owner-span edge admitted. |
| B213 | CAU-04 | — | not_established: no exact owner-span edge admitted. |
| B214 | GRF-03 | — | not_established: no exact owner-span edge admitted. |
| B215 | SCM-02 | — | not_established: no exact owner-span edge admitted. |
| B216 | GRF-01 | — | not_established: no exact owner-span edge admitted. |
| B217 | GRF-01 | — | not_established: no exact owner-span edge admitted. |
| B218 | GRF-03 | — | not_established: no exact owner-span edge admitted. |
| B219 | GRF-02 | — | not_established: no exact owner-span edge admitted. |
| B220 | GRF-02 | — | not_established: no exact owner-span edge admitted. |
| B221 | SCM-01 | — | not_established: no exact owner-span edge admitted. |
| B222 | SCM-01 | — | not_established: no exact owner-span edge admitted. |
| B223 | SCM-02 | — | not_established: no exact owner-span edge admitted. |
| B224 | SCM-03 | — | not_established: no exact owner-span edge admitted. |
| B225 | SCM-03 | — | not_established: no exact owner-span edge admitted. |
| LA-001 | FRY-01 | — | not_established: no exact owner-span edge admitted. |
| LA-002 | FRY-01 | — | not_established: no exact owner-span edge admitted. |
| LA-003 | FRY-03 | — | not_established: no exact owner-span edge admitted. |
| LA-004 | ECO-01 | — | not_established: no exact owner-span edge admitted. |
| LA-005 | DFK-01 | — | not_established: no exact owner-span edge admitted. |
| LA-006 | DFK-01 | — | not_established: no exact owner-span edge admitted. |
| LA-007 | GRF-01 | — | not_established: no exact owner-span edge admitted. |
| LA-008 | HYG-02 | — | not_established: no exact owner-span edge admitted. |
| LA-009 | HYG-02 | — | not_established: no exact owner-span edge admitted. |
| LA-010 | MIG-01 | — | not_established: no exact owner-span edge admitted. |
| LA-011 | HYG-04 | — | not_established: no exact owner-span edge admitted. |
| LA-012 | HYG-04 | — | not_established: no exact owner-span edge admitted. |
| LA-013 | HYG-04 | — | not_established: no exact owner-span edge admitted. |
| LA-014 | SRV-01 | — | not_established: no exact owner-span edge admitted. |
| LA-015 | CTL-01, SRV-03 | — | not_established: no exact owner-span edge admitted. |
| LA-016 | CAU-01, CAU-05 | — | not_established: no exact owner-span edge admitted. |
| LA-017 | LEX-01 | — | not_established: no exact owner-span edge admitted. |
| LA-018 | HYG-02 | — | not_established: no exact owner-span edge admitted. |
| LA-019 | GRF-01 | — | not_established: no exact owner-span edge admitted. |
| LA-020 | API-01 | — | not_established: no exact owner-span edge admitted. |
| LA-021 | CAN-01 | — | not_established: no exact owner-span edge admitted. |
| LA-022 | PLG-01 | — | not_established: no exact owner-span edge admitted. |
| LA-023 | PLG-02, PLG-03 | — | not_established: no exact owner-span edge admitted. |
| LA-024 | SCL-01 | — | not_established: no exact owner-span edge admitted. |
| LA-025 | SCL-03 | — | not_established: no exact owner-span edge admitted. |
| LA-026 | DFK-01 | — | not_established: no exact owner-span edge admitted. |
| LA-027 | DFK-01 | — | not_established: no exact owner-span edge admitted. |
| LA-028 | DFK-02 | — | not_established: no exact owner-span edge admitted. |
| LA-029 | UDF-04 | — | not_established: no exact owner-span edge admitted. |
| LA-030 | UDF-01 | — | not_established: no exact owner-span edge admitted. |
| LA-031 | OBS-01, UDF-01, UDF-02 | — | not_established: no exact owner-span edge admitted. |
| LA-032 | UDF-05 | — | not_established: no exact owner-span edge admitted. |
| LA-033 | REP-01 | — | not_established: no exact owner-span edge admitted. |
| LA-034 | BER-01 | — | not_established: no exact owner-span edge admitted. |
| LA-035 | ECO-01 | — | not_established: no exact owner-span edge admitted. |
| LA-036 | BER-01 | — | not_established: no exact owner-span edge admitted. |
| LA-037 | FRY-01 | — | not_established: no exact owner-span edge admitted. |
| LA-038 | DFI-01, DFI-02 | — | not_established: no exact owner-span edge admitted. |
| LA-039 | EMB-01, EMB-02 | — | not_established: no exact owner-span edge admitted. |
| LA-040 | EMB-03 | — | not_established: no exact owner-span edge admitted. |
| LA-041 | DFI-03 | — | not_established: no exact owner-span edge admitted. |
| LA-042 | EMB-03 | — | not_established: no exact owner-span edge admitted. |
| LA-043 | CLI-01 | — | not_established: no exact owner-span edge admitted. |
| LA-044 | CLI-01 | — | not_established: no exact owner-span edge admitted. |
| LA-045 | REQ-01 | — | not_established: no exact owner-span edge admitted. |
| LA-046 | REQ-01, ACQ-01 | GY-N13b + Atlas DS15: conflicts | No additional plan/register relation established. |
| LA-047 | MIG-05 | — | not_established: no exact owner-span edge admitted. |
| LA-048 | MIG-02 | — | not_established: no exact owner-span edge admitted. |
| LA-049 | MIG-01 | — | not_established: no exact owner-span edge admitted. |
| LA-050 | MIG-04 | — | not_established: no exact owner-span edge admitted. |
| LA-051 | FRC-01, FRC-02 | — | not_established: no exact owner-span edge admitted. |
| LA-052 | PCL-01 | — | not_established: no exact owner-span edge admitted. |
| LA-053 | PCL-01 | — | not_established: no exact owner-span edge admitted. |
| LA-054 | DDM-02 | — | not_established: no exact owner-span edge admitted. |
| LA-055 | DDM-02 | — | not_established: no exact owner-span edge admitted. |
| LA-056 | DDM-01 | — | not_established: no exact owner-span edge admitted. |
| LA-057 | RUN-01 | — | not_established: no exact owner-span edge admitted. |

## Complete-set reading

The complete 282-row table covers every declared B and LA finding and all 291 bundle membership edges; the bundle catalog contains 127 unique bundle entries. The row table is the denominator for this crosswalk. The 273 rows without an admitted task edge are explicitly `not_established`; they are not described as having no runtime dependency.

The DEBT register contains its own live/terminal owner records, but this crosswalk does not bind a finding to one through a shared path string. The 74 currently live/open-or-blocked rows and terminal rows remain owned by the register maintainer; a future relation needs the finding’s scoped owner evidence and the register row’s own owner span. Do not sync or close any register row from this crosswalk.

Pattern pass: P27/P31 (canonical owner), P32/P35 (substance and full denominator), P36 (authority by adjacency), P37/P38 (gate predicate and proxy divergence), P40/P41 (class and attribution). The relation test asks whether the finding’s named owner span and the task’s owner span meet; a path mention elsewhere in a document fails that test.
