"""Adversarial byte, historical-binding and complete-denominator controls."""

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "artifact_verify",
    Path(__file__).resolve().parents[3]
    / "docs/research/e02-cloud-test-plan/implementation-handoffs/D/final-artifact-verifier/verify.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MemoryGit:
    def __init__(self, data: dict[tuple[str, str], bytes]) -> None:
        self.data = data

    def paths(self, ref: str) -> list[str]:
        return sorted(path for revision, path in self.data if revision == ref)

    def blob(self, ref: str, path: str) -> bytes | None:
        return self.data.get((ref, path))

    def run(self, *args: str) -> bytes:
        if args[0] == "diff":
            return "\n".join(self.paths("new")).encode()
        if args[0] == "rev-parse":
            return b"tree\n"
        if args[0] == "cat-file":
            return b"commit\n"
        raise AssertionError(args)


class ArtifactControls(unittest.TestCase):
    def checker(self, blobs: dict[tuple[str, str], bytes]) -> MODULE.Verifier:
        return MODULE.Verifier(MemoryGit(blobs), "new", "old")

    def test_available_filename_is_hashed_as_bytes_before_true_inline_text(self) -> None:
        owner = MODULE.HANDOFF + "receipt.json"
        path = MODULE.HANDOFF + "change.patch"
        payload = b"actual patch file bytes\n"
        checker = self.checker({("new", path): payload})
        checker.walk(
            {"patch": "change.patch", "patch_sha256": hashlib.sha256(payload).hexdigest()},
            owner,
        )
        assert checker.errors == []
        assert checker.counts["sha256_claims_checked"] == 1
        inline = "*** Begin Patch\ninline content\n*** End Patch\n"
        checker.walk(
            {"patch": inline, "patch_sha256": hashlib.sha256(inline.encode()).hexdigest()}, owner
        )
        assert checker.errors == []
        assert checker.counts["inline_utf8_sha256_claims_checked"] == 1
        broken = self.checker({("new", path): payload + b"corruption"})
        broken.walk(
            {"patch": "change.patch", "patch_sha256": hashlib.sha256(payload).hexdigest()},
            owner,
        )
        assert any(v["kind"] == "sha256_mismatch" for v in broken.errors)

    def test_payload_corruption_is_rejected_with_unchanged_labels_and_declared_hash(self) -> None:
        path = MODULE.HANDOFF + "result.txt"
        original = b"PASS\nactual retained payload\n"
        claim = {
            "outcome": "PASS",
            "output": path,
            "output_sha256": hashlib.sha256(original).hexdigest(),
        }
        good = self.checker({("new", path): original})
        good.walk(claim, MODULE.HANDOFF + "receipt.json")
        assert good.errors == []
        bad = self.checker({("new", path): b"PASS\nmutated retained payload\n"})
        bad.walk(claim, MODULE.HANDOFF + "receipt.json")
        assert [v["kind"] for v in bad.errors] == ["sha256_mismatch"]

    def test_old_module_pin_and_old_test_hash_map_survive_later_edits(self) -> None:
        path = "policy-engine/src/polisyos/example.py"
        test = "policy-engine/tests/example.py"
        original = b"old implementation\n"
        changed = b"later implementation\n"
        checker = self.checker(
            {
                ("old", path): original,
                ("new", path): changed,
                ("old", test): original,
                ("new", test): changed,
            }
        )
        checker.walk(
            {
                "target_sha": "old",
                "module_path": "/virtual/archive/" + path,
                "module_sha256": hashlib.sha256(original).hexdigest(),
            },
            MODULE.HANDOFF + "receipt.json",
        )
        checker.walk(
            {
                "implementation_commits": ["old"],
                "test_sources": {test: hashlib.sha256(original).hexdigest()},
            },
            MODULE.HANDOFF + "receipt.json",
        )
        assert checker.errors == []
        assert checker.counts["sha256_claims_checked"] == 2

    def test_raw_absence_is_a_limitation_and_missing_local_artifact_is_an_error(self) -> None:
        checker = self.checker({})
        checker.walk(
            {"raw_log": "raw/missing.txt", "log_sha256": "0" * 64}, MODULE.HANDOFF + "receipt.json"
        )
        assert checker.errors == []
        assert checker.limits[0]["kind"] == "unavailable_raw_or_external"
        checker.walk(
            {"output": "policy-engine/missing.txt", "output_sha256": "0" * 64},
            MODULE.HANDOFF + "receipt.json",
        )
        assert any(v["kind"] == "missing_git_reference" for v in checker.errors)

    def census_fixture(self) -> dict[tuple[str, str], bytes]:
        plan, handoff = MODULE.PLAN, MODULE.HANDOFF
        cell = {
            "path": "policy-engine/tests/example.py",
            "job": "F99",
            "source_sha": "old",
            "reported_state": "PASS",
        }
        finding = {"closure_owner": "X", "bundle_ids": ["X"], "candidate_cells": ["C1", "C2"]}
        mapped = {"findings": {"Z9": finding}, "cells": {"C1": cell, "C2": cell}, "sources": {}}
        data = {
            plan + "execution-organization/finding-owners.tsv": (
                "finding_id\tunit\tsource_closure_owner\nZ9\tD\tX\nA1\tA\tY\n"
            ),
            plan + "execution-organization/bundle-owners.tsv": "bundle_id\tunit\nX\tD\nY\tA\n",
            plan
            + "results/routes.tsv": "finding_id\tunit\tcell_id\nZ9\tD\tC1\nZ9\tD\tC2\nA1\tA\tC3\n",
            plan + "results/cells.tsv": (
                "id\tpath\tjob\tsource_sha\tstate\n"
                "C1\tpolicy-engine/tests/example.py\tF99\told\tPASS\n"
                "C2\tpolicy-engine/tests/example.py\tF99\told\tPASS\n"
            ),
            handoff + "baseline-map.json": json.dumps(mapped),
        }
        return {("new", path): text.encode() for path, text in data.items()}

    def test_census_uses_complete_routes_and_arbitrary_ids_without_fixed_campaign_counts(
        self,
    ) -> None:
        checker = self.checker(self.census_fixture())
        result = checker.census()
        assert (
            result["finding_owner_rows"],
            result["bundle_owners"],
            result["distinct_primary_cells"],
        ) == (1, 1, 2)
        assert checker.errors == []
        fixture = self.census_fixture()
        path = MODULE.HANDOFF + "baseline-map.json"
        mapped = json.loads(fixture["new", path])
        del mapped["cells"]["C2"]
        fixture["new", path] = json.dumps(mapped).encode()
        checker = self.checker(fixture)
        checker.census()
        assert any(v["kind"] == "census_mismatch" for v in checker.errors)

    def test_line_and_byte_locators_reject_shifted_payload(self) -> None:
        path = MODULE.HANDOFF + "received.txt"
        checker = self.checker({("old", path): b"alpha\nbeta\n"})
        source = {"path": path, "commit": "old"}
        doc = {
            "sources": {"s": source},
            "locator": {"source": "s", "lines": [2, 2], "bytes": [6, 11]},
        }
        checker.locators(doc)
        assert checker.errors == []
        doc["locator"]["bytes"] = [5, 10]
        checker.locators(doc)
        assert checker.errors[0]["kind"] == "locator_mismatch"

    def test_malformed_new_json_and_release_fragment_fail_without_marker_checks(self) -> None:
        fixture = self.census_fixture()
        fixture["new", "policy-engine/release-fragments/unreleased/example.toml"] = b"broken = ["
        fixture["new", MODULE.HANDOFF + "new.json"] = b'{"truncated":'
        checker = self.checker(fixture)
        report = checker.run()
        assert report["outcome"] == "FAIL"
        assert {"invalid_json", "invalid_release_fragment"}.issubset(
            {v["kind"] for v in report["errors"]}
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
