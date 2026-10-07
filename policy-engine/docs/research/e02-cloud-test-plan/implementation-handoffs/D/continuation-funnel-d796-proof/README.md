# d796 output transport correction

The adjacent `output.json.gz` now carries 35 complete UTF-8 text members and one verified Git input reference at `/members/funnel-default-scopes-actual~1runner.py`. The 1,657-byte runner body already exists as tracked source at `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/D/continuation-funnel-371-proof/runner.py@9d6169fe182590bbfebcde7f4f75dedc65aa41a3`.

Read `../continuation-funnel-d796-packaging-correction.json` for the current hashes and complete comparison result. It supersedes only the transport/hash fields of the earlier d796 receipt. The original complete-text carrier remains at `output.json.gz@3475b78d9a22e512277f0f348d0acf7432a16f54`, SHA256 `05e93fa822624864130f1de4796f05392ea4824334b0210d566853f820a40a67`.

The root `policyos.e02.complete_output_bundle.v1` envelope is unchanged. This current packaging variant has one object-valued member with `kind=tracked_git_input_ref`; readers must resolve its exact `source_sha:path` through Git, verify the raw bytes against `git_blob`, `sha256` and `bytes`, decode UTF-8, and substitute that text into the member map. Resolving the reference does not execute the runner. Readers requiring the original all-text map can use the immutable original carrier instead.

All other member bodies and their order are unchanged. Substituting the original runner JSON token back into the current uncompressed carrier restores the exact original uncompressed bytes. This correction changes packaging only; runtime source, inputs, complete deciding outputs, verdicts and limitations retain their original source bindings. No runtime was rerun and no original evidence was deleted.
