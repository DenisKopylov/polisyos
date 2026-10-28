# C05 decoder forward fix: Sol narrow source review r1

**GO for this narrow forward fix to Root composition, smoke and the deciding wave.** Overall verification remains Partial; capability `verification_missing`. No product imports or tests were run.

Exact target: `repairs/C05-r8-serialization-contract-r1/manifest.json` SHA-256 `ec27fc5f6c21af0c84c4ef2bac43fae980f95bed6ffc73868858523cb6e8b9c3`; patch SHA-256 `9d3b1a9e5c193ea6f9d77c3043b1465db9921c7ad9c9d3b6a38a13a62fa38fec`. Base `545c6990e2bfa42bf580b475e23cf88df04e71d8`, tree `abd7d9913680d5531081c45536c1cf7d7d701835`.

I independently reconstructed both complete postimages from their pinned Git preimages, checked their blob/SHA-256/byte identities and linked artifact hashes, parsed both Python files, and found both current canonical preimages matching. This establishes the exact two-file delta, not executable verification.

The sole mechanism change supplies `source="polisyos.scientist.orchestration.llm.prepared_request"` to the existing canonical `decode_json_object` call. The actual shared signature requires that keyword. Its strict decoder, kind label and result path are unchanged; no catch, permissive alternative, cache miss or authority fallback is added. This is the **SAME shared-consumer API compatibility class** as the corrected r8 finding.

The existing test module gains a positive through the actual wire and lossless native helpers, checking nested tuple/list preservation. Six malformed-input cases cover invalid UTF-8, duplicate keys, nonfinite value, overflowing value, non-object root and truncated JSON; they require `ValueError` and both stable source/kind diagnostics. Those assertions match the unchanged canonical decoder's refusal branches. Tests remain UNRUN here.

The packet manifest explicitly leaves the broader census companion pending. Its README census prose is not proof used for this narrow verdict. The separate Sol shared-contract audit records the whole changed-call selector and unresolved boundaries. No additional finding from that bounded audit delays this concrete fix.

Root should compose and read back the exact checkpoint, run the corrected positive strict-decoder/native/wire smoke and full actual Gateway/preflight/research POST consumers, and then run semantic removals. A removal failure counts only at the intended assertion after the positive baseline passes, followed by exact restoration and a passing replay. Type, architecture, API, generated and compatibility gates remain required.

Original r8 reviews remain frozen. `C05-r8-code-sol-correction-r1.md/json` corrects my earlier GO to HOLD for the unrepaired batch. This separately reviewed fix does not rewrite either history or imply runtime PASS.

Independent evidence: `C05-r8-serialization-contract-sol-r1.json` SHA-256 `7920b9b88b74c615edc0ddb85d0ef93e4f35f592bff52e002403e99d071f005e`. Only new RAW review files were written; no canonical source, Git state, environment or children changed.
