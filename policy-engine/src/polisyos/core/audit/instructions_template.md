Install verifier dependencies:

```bash
pip install -r verification/requirements.txt
python verification/verify.py
```

## Verification workflow

1. Validate package checksums (`verification/checksums.sha256`).
2. Validate detached signature of checksum manifest (`verification/checksums.sha256.sig`) if present.
3. Verify CAS artifacts and signatures.
4. Validate provenance graph in `provenance/prov.json`.
5. Review `verification/report.md` (if generated).

## Profiles

- `full`: blobs + manifests included, full CAS verification.
- `manifests_only`: blob payloads omitted; verifier runs indirect signature/integrity checks.

## Security notes

- Extract archives only with trusted tooling.
- Package keys are **not** trusted by default.
- Prefer providing explicit trusted keys to verifier.
