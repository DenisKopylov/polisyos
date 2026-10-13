# R1212 addendum: R1188 reference comparison assertion

Verdict for the frozen R1188 packet: **BLOCK the current test patch until this assertion is corrected**. The proposed production DTO change remains structurally sound for the previously reviewed scope; this is a new test-oracle defect, not a source-behavior escape and not a reason to alter the DTO.

## Exact finding

In the frozen patch `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/r1188-abm-execution-source-dto-companion-20261013/proposal.patch` (SHA-256 `28b9c17901438560d82af2343d53bf39514a46bba4a5219fb45e5be116f32b9c`), the new parameterized round-trip test adds:

```python
assert result.execution_input_basis_ref == simulation.execution_input_basis_ref
if result.execution_input_basis_ref is not None:
    assert type(result.execution_input_basis_ref) is not type(
        simulation.execution_input_basis_ref
    )
```

The two objects intentionally have different Pydantic model classes. The IR value is `_ABMExecutionInputBasisArtifactRef(ArtifactRefModel)`; the Core value is `FoundryExecutionInputBasisRef(ArtifactRef)`. Neither class is generic. The first assertion therefore fails for the non-null `single_step_basis` parameter before the following type-distinction assertion can pass.

This follows directly from the installed Pydantic 2 BaseModel equality implementation at `policy-engine/.venv/lib/python3.14/site-packages/pydantic/main.py` (SHA-256 `5994f1c16f358a097be58d34cc72499a8537a82352cbed4a084984b013dfb624`): its model comparison first requires equal concrete types (or matching generic origins), then compares fields. These ref classes have distinct concrete types. Their nested ArtifactID classes are also separately defined in the IR and Core packages. No test was run; this conclusion is based on the concrete class hierarchy and the equality implementation.

The other two parameterized rows have a null basis ref and do not expose this failure. The single-step row is a required positive control, so the new test suite cannot pass as written.

## Correct oracle

Compare the normalized reference identity rather than cross-class Pydantic objects. The comparison must include artifact ID, kind, media type, and manifest_profile_sha256. For example, compare a normalized JSON-mode dump or an explicit tuple using the string form of artifact_id and the other three fields. Keep the separate assertion that the IR and Core ref types differ. This preserves the test's purpose: verifying all selected-reference identity fields across a deliberate layer-specific type conversion.

This is a P38 proxy-gate finding: the required property is preservation of reference identity, while the test currently measures concrete model equality. The divergent case is the intended pair of distinct IR/Core ref classes with matching field values.

## Current binding and scope

At current HEAD `691b0082846279f318c54a8e5618807a0d810698`, tree `eb4ab69bf76126a07a9585755aba68b7197ea75f`, frame R1210 SHA-256 `31687de984b4625c20d358d57b031ef44c6fff5c03e38095655ef23f2e8c1779`, the two target source files still match the R1188 frozen preimages: IR source `1f87901cf69a44b480350dc896a18ed0340bcbbffa5e2505a14eadaa81a1f939`; test `7c51c0ca869a0c110b9567bba70366fb120df91fb3bd4a30f05080fd95bad354`. The source patch remains virtual and unapplied.

This finding does not change the earlier source review: the DTO's typed fields and schema/status/ref validator can proceed after the test oracle is fixed. R1183's live coupled producer regressions still need root's post-composition run. Generated schema/catalog review and the ABM/CAS version decision remain publication companions.

Classification: NEW test-oracle defect, separate from the shared strict-DTO consumer gap. No formal closure is claimed; closure IDs remain empty.
