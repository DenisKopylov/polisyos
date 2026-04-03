# Audit (`polisyos.core.audit`)

`core.audit` assembles portable audit archives from CAS artifacts and run metadata, then verifies
them offline. The output is a deterministic `.polisyos-audit.tar.gz` bundle that can be checked
without the original runtime.

## Role in System

- **Depends on:** `core.artifacts` for CAS and `core.contracts.provenance` for merged provenance shapes.
- **Used by:** runtime tooling, security/compliance flows, and export workflows for governed runs.
- **Boundary function:** packages the evidence needed for external review and reproducible verification.

## Key Concepts

- **Assembler** - builds the archive tree, checksums, and optional signature material.
- **Verifier** - validates integrity, signatures, provenance, and optional SLSA/SBOM material.
- **Safe extraction** - `safe_tar.py` prevents unsafe archive unpacking.
- **Markdown reports** - `report.py` renders verifier output into human-readable summaries.
- **Templates** - the package ships both instructions and a standalone verifier template.

## Public API

- `AuditPackageAssembler`
- `AuditPackageVerifier`
- `ExportOptions`
- `ExportProfile`
- `SigningPolicy`
- `VerificationReport`
- `render_markdown`

## Current State

- Last updated: 2026-04-03
- The audit bundle still includes provenance, manifest, and signature material, with optional SLSA/SBOM extras.
- The tree now includes `instructions_template.md` and `standalone_verifier_template.py` as part of the package docs/tooling surface.
