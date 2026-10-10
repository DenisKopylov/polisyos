# L01 serving-context and L6 custody preflight

Date: 2026-10-09. This is a read-only follow-up to the T1/T2 intake. It corrects the availability scope for the private L01 receipts and records the exact L6 source binding that was re-read. It does not update an original finding, authorize a protected effect, or claim formal closure.

## Scope and inputs

Candidate source was `077a572ff5880b3f50a85d3e3db6a232d277659a` / tree `2895b6c7597215b714275cb4ba83a504724dc89c`. The paired roots named by [`INPUTS.json`](../../../execution-prompts/unified-local-2026-10-09/INPUTS.json) `@aae5062459b2afdd8f894ed0ca63b5a684f17fcf` were available at L01 `25333d87e3e32795e2e89288d5f2bd70e8e756c9` and L02 `c3b171010a7ce30b12d1dbd497eb646b9147afa0`.

I read and SHA-256 hashed the 18 already named paired JSON metadata inputs and only the three root-nominated L6 member files listed below. This is an exact selected subset, not a complete source census. No raw payload copy or broad payload census was made.

| Alias | Selected file | SHA-256 |
|---|---|---|
| L01 | `parallel-20261008-l01/delivery.json` | `25debd15d8d6519f4d677fa59d8c378570f53d2f0e688a3a73cd8edf5cd8be7a` |
| L01 | `parallel-20261008-l01/packets/A.json` | `09be5b5b98e9daeb61f0704e7f50f247f1e17db924c535ee8a0ec4a564597b38` |
| L01 | `parallel-20261008-l01/packets/B.json` | `b2ea97c8e1e9001e33e5c96a15208809d283117d429b0bc97d2a41c256c41ac5` |
| L01 | `parallel-20261008-l01/packets/C.json` | `17f80b522b01e0c25385c250bb0411af98d033fed1972e07d238015d483a5f77` |
| L01 | `parallel-20261008-l01/packets/D.json` | `16b8538556a1276ce8fe161a8aff365a171907ae12522a63a31a3f48098a8fdb` |
| L01 | `parallel-20261008-l01/packets/E.json` | `33cd59170e758302c4ae11317a3f24ee30047d7db0abfed97a786e4f40274ed8` |
| L01 | `parallel-20261008-l01/packets/F.json` | `74c27a7a1ce1e57b188eb255cc298a6c25ab407779a4cb944c3da4f0a85b0dc4` |
| L01 | `parallel-20261008-l01/host-inventory.json` | `be9e5c516dfede510205d9f6779141a67aa7f2f35825969a488a21ac8c079ef8` |
| L01 | `parallel-20261008-l01/api-census.json` | `2673270240219d4d49026ffcc83aaa7c81777fd2ac0ee99e990017c408c8c532` |
| L01 | `custody-version-20261008/handoffs/L6.json` | `9c358ac47893e9b4945488b97422c8ef00be63af0f980f7ce2b39f15fe996658` |
| L01 | `custody-version-20261008/handoffs/Legal.json` | `6e29efb479ef56edd05d0a13f8cffce30e784e97d0c0edd7b148ec368fc90172` |
| L01 | `custody-version-20261008/handoffs/I3.json` | `2c8d35e2d87d2a53a4c75e06bc7df1049d0f3268c6e405bc2d1c7b8d8983bd63` |
| L02 | `parallel-20261008-l02/manifest.json` | `c8b83ebe68bbd3568d9bceb7626863c3acb5616ab2c717bf2a3d13130b0cc769` |
| L02 | `parallel-20261008-l02/prepared/l02_late_input_independent_review.json` | `8f06c226e12132c91b836507d014cbc161f53f998054817edabdee20d941c347` |
| L02 | `parallel-20261008-l02/prepared/l02_protected_ab.json` | `49ec47048de9ff39ff8f38f217cd2bf7bcd3e8640e089600c312c1930f19a5d9` |
| L02 | `parallel-20261008-l02/prepared/l02_protected_d.json` | `520c92f31d26e6973071b78f1e43b2c7f8ae842bb02e7a99aca3f679cde77250` |
| L02 | `parallel-20261008-l02/prepared/l02_protected_e.json` | `e799113371758ce768a2356393e9979d970fac4c1f01cdcdb85ed3af29d103a9` |
| L02 | `parallel-20261008-l02/prepared/l02_source_rights.json` | `1dc7c61b533dae0a39f199394e007a3077f93bed7d0cd69e5944f4d49e574300` |

The L01 factual packets continue to state `production_input_admission=not_established` and `input_bytes_digest=withheld_no_disclosure_admission`. L02's independent correction says the published L01 packets exist but do not establish the task-specific joined owner/input/profile/API tuple. These are bounded custody observations, not proof that a source or owner is absent.

## Exact L6 resolution and comparison

The named private receipts are available in the L01 custody checkout, though unavailable at the same exact paths in the candidate and primary worktrees: `root-manifest.json` SHA-256 `b893eb0590cf151afd89ed0cb0c288fddf09a93f3e36305679e33aaeb55dd6c3`, `l6-selected-bindings.json` `551c1b66cd0644d6e7a29492d51952d7e18b3406c3fb5921ae9b6c6e3a1bc491`, and `public-alias-index.json` `db427943dfd71c99ad1bf405f24a145b8769eb04f91a0de0f2bc0ddf40bd49b2`. This narrows the earlier statement that they were missing in the candidate and primary; it does not change their absence from those two worktrees.

The root receipt's exact locator resolves to an existing local `manifest.json`; its measured SHA-256 `9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105` equals the receipt's `sha256_private`. Its physical directory resolves to the primary `policy-engine/production_data` root (the candidate path resolves to the same target). I followed only the selected root manifest, its named Ukraine-simulation bundle manifest, and three nominated members. I did not walk the directory.

The root manifest declares `default_runtime_profile=research`, `generated_at=2026-05-10T00:00:00Z`, and `ukraine_simulation.version_id=ukraine_agent_simulation_baseline_20260410`. Its nominated `FINAL_ARTIFACTS_MANIFEST.json` exists; its SHA-256 `e65ca699c56b203097c5dc11d99fd171a337e89ee888132ce82e36557d87992d` matches the root manifest's artifact checksum. Under the exact three-member denominator in `l6-selected-bindings.json`:

| Member | Declared size / SHA-256 | Observed size / SHA-256 | Result |
|---|---|---|---|
| `L01_L6_KNOBS_01` | 268 / `4f52f0a743a46f5c53cf5608cc73b1b05f0e8d7f8ee360d866e6f127863a840f` | 581 / `005d89f0ab1728a4f6c20cccad5781c1ef7721f82215c8de7c21622f3abe4328` | size and digest differ |
| `L01_L6_LEXMAP_01` | 178 / `49168c4779a0d1025c166f7eea04477efdd27fb3a3b7554ae7878da45af7fbaa` | 972 / `5c72461237a09605c39f180345de45cff55c59eed5d4d0e2ca80cc4aa446addf` | size and digest differ |
| `L01_L6_OBSERVATION_ROUTES_01` | 3021 / `6d565e724d4caf89841499ba31df47d0a8c0dcc800689ea159cfab608d4b382b` | 3021 / `6d565e724d4caf89841499ba31df47d0a8c0dcc800689ea159cfab608d4b382b` | exact match |

Each member path was resolved from the root-manifest-selected bundle directory and checked to remain inside that directory before hashing. The manifest's own producer-root field is a separate source-side path; no serving-context evidence equates it to a live runtime root. The result is a real local metadata/content-binding positive for the root checksum and route member, and a real descriptor mismatch for knobs and Lex map. It is not a valid L6 served-input or protected-effect positive.

The alias index points `L01_L6_BUNDLE_MANIFEST_01` at `private/ukraine-bundle-manifest.json`, resolved relative to the named run root. The record is available (SHA-256 `e357236d05c1924ff20de5586e37c9b609e0a97dbb5f24653b743b7cc95ac828`); its `metadata_private` is the same parsed manifest as the root-manifest-nominated `FINAL_ARTIFACTS_MANIFEST.json`, and its `sha256_private` equals that file's `e65ca699c56b203097c5dc11d99fd171a337e89ee888132ce82e36557d87992d`. Its knobs and Lex-map descriptors remain 268/178 and do not match the current selected members. This is a second custody view of the same manifest, not a versioned replacement. The record path was first resolved against the wrong directory; I corrected it against the alias-index run-root convention before concluding. The other two index entries point to a configured Lex database version and `legal_kg_db_path`; those identify a distinct database snapshot, not the `lex_intervention_map.json` member. The selected root names one `ukraine_simulation` version and no alternate matching manifest. Within this exact alias/receipt scope, I found no existing source-owned versioned replacement for the two changed members. I did not search other versions or directories.

The source-qualified prior receipts remain useful: `packets/A-l6.json` SHA-256 `c6ab16fa192483dbfaccca6b634e79129709e6d2ba6f7b05d9e152090a3bf61f`, `evidence/binding-readback.json` `d3c8e15fa6a76e93703db0e38e837c7c1b5597674e0716943de04a29f7025e43`, and `source.json` `5092071cf08f36358a3eb00b77e3169ea5dbf47a02e4141fcca5bf75baf38d38`. The L6 packet labels the manifest profile/version/time `owner_supplied`, the exact hash comparisons `recomputed`, and current custodian, replacement legitimacy, relocation/currentness, admitted purpose, and served path `not_established`.

## Serving-instance and authority boundary

The current source resolver at `production_data.py@2a07d333f6272328e171a5c9f641420c2c419abf` selects `params["production_data_root"]`, then `POLISYOS_PRODUCTION_DATA_ROOT`, then (when `allow_default=True`) a working-directory-relative `production_data` or `policy-engine/production_data`. The current task shell had neither `LOCAL_DATA_ROOT_01` nor any `POLISYOS_*`/`POLICYOS_*` environment setting. A read-only listener snapshot showed no PolicyOS/Python/uvicorn runtime listener; the only listeners were unrelated system processes. No source API URL, runtime process context, or request was supplied. I made no HTTP request and started no server.

Therefore the actual request-selected root/profile/context and consumer readback remain `not_established`. The manifest's `research` default is an internal configuration assertion, not a served profile. The local root manifest and member digests establish file identity for the exact selected files; they do not establish current ownership, external permission, publication, reuse rights, or commit-time authority. No generic external issuer is inferred. This is an L6 substrate-binding question; alias-only criteria such as LA-018 retain their original no-issuer semantics.

P37 labels for this check: root profile/version/time are `owner_supplied`; root-to-bundle and member byte comparisons are `recomputed`; actual runtime root/profile, active custodian, replacement validity, and currentness are `not_established`. P38 divergence: the property is “the current served consumer resolved the admitted L6 bundle”; the check executed is “these named local bytes match this root-manifest-nominated descriptor.” A request-level `production_data_root` can select a different root while this offline hash check stays unchanged. No live consumer was available to distinguish those cases.

## G intake and next check

The minimum next input is the nominated bundle custodian's existing matching manifest/bytes pair, or an already-versioned replacement manifest for the exact knobs and Lex-map members, plus the responsible source owner and the applicable profile's validity/currentness. This packet does not identify an appointed custodian identity or a current API. The source owner should also name the existing configured alias, selected root/profile, API/consumer, purpose, and served-root identity. For a protected action, the exact original permit issuer/verifier and writer-bound revocation protocol are additional; they must not be invented from this data manifest.

Two bounded choices for G:

1. **A — source-bound input available:** resolve only the custodian-supplied existing manifest and its named members; recompute the exact descriptor bindings; obtain a read-only fresh response from the named live API and compare its root/profile/context to that same source record; then invoke `default_l6_bundle_paths → load_l6_intervention_substrate → generation_cycle._value_method_route_constraint` for that same input. Keep source identity and permission distinct from hashes.
2. **B — no matching owner/input supplied:** retain the original held/limited result and record L6 source positive as `input_missing` or `verification_missing`, and serving positive as `consumer_missing`/`bridge_missing`. This does not establish global source absence and does not create a new issuer contract.

P40 bucket: the knobs and Lex-map discrepancies are the second instance of the same `manifest descriptor versus member bytes` class. Stop with that class; do not repair files one by one. Widen only through one owner-provided matching versioned bundle, or retain the bounded residual above. The falsifier is already concrete: keeping manifest/profile declarations fixed, the selected member comparisons reject both changed members while the route control still passes. No production file, manifest, descriptor, or source code was changed; no tests or protected effects were run; no formal G closure is claimed.
