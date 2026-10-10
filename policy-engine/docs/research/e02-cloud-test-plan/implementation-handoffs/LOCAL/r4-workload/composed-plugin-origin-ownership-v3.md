# Pytest origin ownership capture v3 proposal

This unapplied patch is LOCAL/raw/composed-plugin-origin-ownership-v3.patch, SHA-256 b7ec25da08a2f7fb222b8071048b984cbdeede0f8a68d4327b4395cfa85e6719. It targets the currently applied v2 plugin bytes at LOCAL/raw/composed_mac_pytest_origin_plugin.py, SHA-256 787f22ff049d36d897c58707fd70bc115b9e8e01b707803f42e3797d66f02fa2. The plugin itself was not edited.

## Change

P40 bucket: SAME_CLASS_DEEPER. V2 still relied on packages_distributions() to name candidate distributions. The live sidecar showed seven file-backed origins for which that name mapping returned no candidate even though the actual origin belongs to an installed distribution. The patch replaces that ownership proxy with one generic installed-file inventory. It walks every distribution returned by importlib.metadata.distributions() in the child process; the supplied live diagnosis reports 248 installed distributions, but the proposed denominator is dynamic and recorded rather than hardcoded:

- Enumerate every importlib.metadata.distributions() result and each available distribution.files entry.
- Resolve each entry through distribution.locate_file(entry) and index its normalized absolute path. Do not import the package and do not read or hash package payloads during inventory construction.
- For each already-loaded external top-level root, require an exact observed-origin path match. A package-name alias, site-root location, or an unrelated distribution file does not establish ownership. Multiple matching records are ambiguous.
- Only after identifying a unique exact record, read and hash that selected origin and compare available RECORD hash/size facts. A mismatch, malformed record, missing unique owner, or unresolved inventory prevents package-version resolution.
- Record the actual distribution count, file-entry count, and inventory issue count. Any incomplete installed-file inventory leaves owner uniqueness unestablished and the aggregate capture partial; an enumeration failure is not_established.

The ownership path no longer calls packages_distributions(). distribution_mapping_status is retained as not_used_for_ownership so the output cannot be mistaken for a successful name-based proof. The environment remains limited to one observed origin per loaded top-level import root; each row retains all loaded submodule names, but the patch does not claim per-submodule provenance or exhaustive package-payload inventory.

## Live baseline and bounded unknowns

The retained baseline sidecar is LOCAL/raw/plugin-process-environment-live-20261010/origins-45338.json, SHA-256 b2642121fde7f3910736b5cb794c46683b30c4e5b20f2fa81dbcb043fc0cc880. It contains 103 external top-level rows: 94 currently resolved and 9 unresolved. The unresolved rows are __main__, __mp_main__, _csparsetools, _cyutility, _loss, _moduleTNC, _ni_label, _virtualenv, and opentelemetry.

The first seven are the target of this generic inventory widening: they are file-backed origins whose owner can be looked up by exact path across installed distribution files, without relying on the import-name alias map. This is a proposal expectation from the supplied live diagnosis, not a v3 execution result.

The final two stay honest and unresolved. _virtualenv.py is generated environment bootstrap code without an installed-file RECORD owner; the patch must not invent a distribution version from its site-packages location. opentelemetry is observed as a namespace directory, not one installed regular file; the patch must not assign it to one of its several candidate distributions or drop it. These rows prevent a complete capture; the aggregate remains partial unless another incomplete root or inventory makes it not_established. An unknown inventory row is evidence of an unresolved boundary, not evidence of a clean complete environment.

The strict manifest bridge remains unimplemented. A future bridge may project only selected rows whose origin, exact owner, version, and applicable RECORD checks are actually resolved. It must preserve and require the whole loaded_external_import_capture_status and distribution_inventory_status; selecting a resolved subset from a partial capture cannot be labeled a complete runtime profile. Product-tree modules continue to bind to the independently frozen source manifest. The proposed sidecar alone does not qualify the strict environment profile.

## Executable in-memory falsifiers for root review

These snippets use fake distribution metadata and temporary selected files. They are not executed here. Load the patched plugin source as capture_plugin; the fake Distribution.files and locate_file methods are the in-memory interfaces under test.

    import base64
    import hashlib
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    from unittest.mock import patch

    class Entry:
        def __init__(self, name, digest=None, size=None):
            self.name = name
            self.hash = (
                SimpleNamespace(mode="sha256", value=digest)
                if digest is not None
                else None
            )
            self.size = size

        def __str__(self):
            return self.name

    class Distribution:
        def __init__(self, root, name, version, entries):
            self.root = Path(root)
            self.metadata = {"Name": name}
            self.version = version
            self.files = tuple(entries)

        def locate_file(self, entry):
            return self.root / entry.name

    def capture_for(origin, distributions, purelib, product_root):
        module = SimpleNamespace(__spec__=SimpleNamespace(origin=str(origin)))
        paths = {
            "purelib": str(purelib),
            "platlib": str(purelib),
            "stdlib": str(product_root / "stdlib"),
            "platstdlib": str(product_root / "stdlib"),
        }
        distribution_lookup = {
            item.metadata["Name"]: item for item in distributions
        }
        with patch.object(capture_plugin.sysconfig, "get_paths", return_value=paths):
            with patch.object(
                capture_plugin.importlib.metadata,
                "distributions",
                return_value=distributions,
            ):
                with patch.object(
                    capture_plugin.importlib.metadata,
                    "distribution",
                    side_effect=distribution_lookup.__getitem__,
                ):
                    with patch.object(
                        capture_plugin.importlib.metadata,
                        "packages_distributions",
                        return_value={"probe_pkg": ["unrelated-dist"]},
                    ):
                        return capture_plugin.build_process_environment_manifest(
                            {"probe_pkg": module}, product_root
                        )


    with tempfile.TemporaryDirectory() as root_value:
        root = Path(root_value)
        purelib = root / "site"
        purelib.mkdir()
        product_root = root / "product"
        product_root.mkdir()

        # A deliberately false package-name mapping must not attribute another file.
        shadow = purelib / "shadowpkg.py"
        shadow.write_bytes(b"loaded bytes")
        unrelated = Distribution(
            purelib, "unrelated-dist", "9.9", [Entry("unrelated.py")]
        )
        result = capture_for(shadow, [unrelated], purelib, product_root)
        row = result["loaded_external_import_origins"][0]
        assert row["distribution_owner_status"] == "not_established"
        assert row["package_version_status"] == "not_established"
        assert result["loaded_external_import_capture_status"] != "complete"

        # A filesystem origin outside configured roots is retained, not omitted.
        offsite = root / "outside" / "orphan.py"
        offsite.parent.mkdir()
        offsite.write_bytes(b"orphan")
        result = capture_for(offsite, [], purelib, product_root)
        row = result["loaded_external_import_origins"][0]
        assert row["origin"] == str(offsite)
        assert row["distribution_owner_status"] == "not_established"
        assert result["loaded_external_import_capture_status"] != "complete"

        # Exact file membership with an incorrect RECORD digest cannot resolve version.
        selected = purelib / "recorded.py"
        selected_bytes = b"observed file bytes"
        selected.write_bytes(selected_bytes)
        bad_digest = base64.urlsafe_b64encode(
            hashlib.sha256(b"different bytes").digest()
        ).decode("ascii").rstrip("=")
        owner = Distribution(
            purelib,
            "record-owner",
            "1.2.3",
            [Entry("recorded.py", digest=bad_digest, size=len(selected_bytes))],
        )
        result = capture_for(selected, [owner], purelib, product_root)
        row = result["loaded_external_import_origins"][0]
        assert row["distribution_owner_status"] == "resolved"
        assert row["distribution_checks"][0]["record_integrity_status"] == "mismatch"
        assert row["package_version_status"] == "not_established"

Reintroducing package-name mapping as ownership while keeping the fake mapping and version but skipping exact file membership would make the first assertion detect false attribution. Omit off-site roots from the external rows and the second assertion would detect silent disappearance. Ignore RECORD mismatches while keeping the exact owner and the third assertion would detect a version resolved from unverified file content.

No patch application, pytest/test, product command, external package import, or heavy workload was run for this proposal.
