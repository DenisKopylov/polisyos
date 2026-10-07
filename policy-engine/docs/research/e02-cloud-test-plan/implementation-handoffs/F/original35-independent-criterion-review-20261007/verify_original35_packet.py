"""Verify the noncanonical F criterion-review packet against immutable Git bytes.

No checkout, network, product execution or ledger writes. Historical unavailable
nondeciding provenance is deliberately not promoted to measured custody PASS.
"""
from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import io
import json
import lzma
import pathlib
import platform
import subprocess
import sys
import time
from collections import Counter


def digest(data):
    return hashlib.sha256(data).hexdigest()


class Review:
    def __init__(self, repo):
        self.repo = repo
        self.cache = {}
        self.receipts = set()
        self.materials = set()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo)

    def body(self, ref, path):
        key = (ref, path)
        if key not in self.cache:
            self.cache[key] = self.git("show", f"{ref}:{path}")
        return self.cache[key]

    def ref(self, spec):
        ref = spec.get("git_ref", spec.get("head"))
        data = self.body(ref, spec["path"])
        assert len(data) == spec["bytes"], f"stored bytes: {spec['path']}"
        assert digest(data) == spec["sha256"], f"stored hash: {spec['path']}"
        if "git_blob" in spec:
            assert self.git("rev-parse", f"{ref}:{spec['path']}").decode().strip() == spec["git_blob"]
        return data

    @staticmethod
    def pointer(value, pointer):
        for key in pointer.strip("/").split("/"):
            key = key.replace("~1", "/").replace("~0", "~")
            value = value[int(key)] if isinstance(value, list) else value[key]
        return value

    def material(self, carrier, spec):
        data = self.ref(dict(spec, git_ref=carrier))
        encoding = spec.get("encoding", "raw")
        if encoding in ("raw", "identity"):
            decoded = data
        elif encoding in ("gzip", "gzip-lossless", "gzip-lossless-utf8"):
            decoded = gzip.decompress(data)
        elif encoding in ("xz", "xz-lossless"):
            decoded = lzma.decompress(data)
        elif encoding in ("json-escaped-utf8", "utf8-json-string"):
            decoded = json.loads(data).encode("utf-8")
        else:
            raise AssertionError(f"unsupported explicit encoding {encoding}")
        raw_n = spec.get("raw_bytes", spec.get("decoded_bytes"))
        raw_h = spec.get("raw_sha256", spec.get("decoded_sha256"))
        assert raw_n is not None and raw_h is not None, f"decoded binding absent: {spec['path']}"
        assert len(decoded) == raw_n and digest(decoded) == raw_h, f"decoded hash: {spec['path']}"
        self.materials.add((carrier, spec["path"]))

    def verify(self, packet):
        source = packet["source"]
        for name in ("common", "ROOT072_audit", "ROOT072_index", "ROOT072_report", "owner_TSV", "bundle_TSV"):
            self.ref(source[name])
        assert self.git("rev-parse", source["product_sha"] + "^{tree}").decode().strip() == source["product_tree"]
        all_owners = list(csv.DictReader(io.StringIO(self.ref(source["owner_TSV"]).decode()), delimiter="\t"))
        all_bundles = list(csv.DictReader(io.StringIO(self.ref(source["bundle_TSV"]).decode()), delimiter="\t"))
        owners = {x["finding_id"]: x for x in all_owners if x["unit"] == "F"}
        bundles = {x["bundle_id"]: x for x in all_bundles if x["unit"] == "F"}
        assert len(all_owners) == 282 and len(all_bundles) == 127
        rows = packet["rows"]
        ids = [x["finding_id"] for x in rows]
        assert len(ids) == len(set(ids)) == 35 and set(ids) == set(owners)
        assert len(bundles) == 17 and sum(len(r["original_card_refs"]) for r in rows) == 36
        assert packet["denominator"] == {"all_TSV_findings": 282, "all_TSV_bundles": 127, "F_IDs": 35, "F_bundles": 17, "original_bindings": 36, "unique_original_blocks": 35, "LA016_ID_count": 1, "LA016_bindings": 2}
        for row in rows:
            fid = row["finding_id"]
            assert row["primary_owner_from_full_TSV"] == owners[fid], f"owner {fid}"
            assert row["bundle_owner_from_full_TSV"] == bundles[owners[fid]["source_closure_owner"]]
            refs = row["original_card_refs"]
            assert len(refs) == (2 if fid == "LA-016" else 1)
            for ref in refs:
                raw = self.body(ref["source_sha"], ref["source_path"])
                lo, hi = ref["lines"]
                block = b"".join(raw.splitlines(keepends=True)[lo - 1:hi])
                assert len(block) == ref["bytes"] and digest(block) == ref["sha256"], f"card {fid}"
                assert block.decode() == row["original_text"]
                assert block.decode().startswith(ref["title"] + "\n") and ref["title"].startswith(f"## {fid}. ")
                assert ref["criterion_id"] == fid
                assert self.git("rev-parse", ref["source_sha"] + ":" + ref["source_path"]).decode().strip() == ref["document_git_blob"]
            sci = row["scientific_implementation"]
            assert self.git("rev-parse", sci["sha"] + "^{tree}").decode().strip() == sci["tree"], f"code tree {fid}"
            self.ref(row["deciding_per_ID_carrier_ref"])
            for ref in row["deciding_receipt_refs"]:
                obj = json.loads(self.ref(ref))
                self.receipts.add((ref["git_ref"], ref["path"]))
                if ref.get("json_pointer"):
                    self.pointer(obj, ref["json_pointer"])
            recommendation = row["independent_original_criterion_recommendation"]
            assert recommendation["check"] in ("PASS", "FAIL", "ERROR", "SKIP", "UNRUN")
            assert recommendation["outcome"] in ("closed", "limited", "held", "open")
            assert recommendation["not_formal_G_closure"] is True
        assert dict(Counter(r["independent_original_criterion_recommendation"]["outcome"] for r in rows)) == packet["original_recommendation_counts"]
        assert dict(Counter(r["independent_original_criterion_recommendation"]["check"] for r in rows)) == packet["original_check_counts"]
        for record in packet["raw_receipt_check_registry"]:
            spec = record["receipt"]
            obj = json.loads(self.body(spec["git_ref"], spec["path"]))
            actual = self.pointer(obj, record["pointer"])
            assert actual.get("outcome", actual.get("check", "UNRUN")) == record["raw_outcome"]
            assert actual.get("target_sha") == record["target_sha"]
        for spec in packet["fresh_independent_review_refs"].values():
            self.ref(spec)
        for publication in packet["published_owner_materials"]:
            carrier = publication["receipt"]["git_ref"]
            obj = json.loads(self.ref(publication["receipt"]))
            if publication.get("manifest_ref"):
                manifest = json.loads(self.ref(publication["manifest_ref"]))
                records = manifest["records"] if isinstance(manifest, dict) else manifest
            else:
                records = self.pointer(obj, publication["manifest_pointer"])
            assert len(records) == publication["record_count"]
            for record in records:
                self.material(carrier, record)
        assert packet["recommendation_is_not_G_accepted"] is True
        assert packet["custody"]["all_reference_custody_check"] == "UNRUN"
        assert packet["custody"]["historical_non_deciding_reference_check"] == "UNRUN"
        assert packet["new_DiD160_or_RDD4000_coverage_wave"] is False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--packet", required=True)
    parser.add_argument("--negative-controls", action="store_true")
    args = parser.parse_args()
    start = time.monotonic()
    path = pathlib.Path(args.packet)
    raw = path.read_bytes()
    if path.suffix == ".gz":
        raw = gzip.decompress(raw)
    packet = json.loads(raw)
    review = Review(args.repo)
    issues = []
    try:
        review.verify(packet)
    except (AssertionError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
        issues.append(str(exc))
    negatives = []
    if not issues and args.negative_controls:
        controls = (
            ("missing-ID", lambda p: p["rows"].pop()),
            ("wrong-owner", lambda p: p["rows"][0]["primary_owner_from_full_TSV"].update(source_closure_owner="CAU-03")),
            ("wrong-title", lambda p: p["rows"][0]["original_card_refs"][0].update(title="## B204. Wrong title")),
            ("stale-receipt-hash", lambda p: p["rows"][0]["deciding_receipt_refs"][0].update(sha256="0" * 64)),
            ("wrong-code-tree", lambda p: p["rows"][0]["scientific_implementation"].update(tree="0" * 40)),
            ("duplicate-LA016", lambda p: p["rows"].append(copy.deepcopy(next(r for r in p["rows"] if r["finding_id"] == "LA-016")))),
        )
        for label, mutate in controls:
            changed = copy.deepcopy(packet)
            mutate(changed)
            try:
                review.verify(changed)
                negatives.append({"control": label, "validator_check": "PASS", "harness_check": "FAIL"})
            except (AssertionError, KeyError, ValueError, subprocess.CalledProcessError) as exc:
                negatives.append({"control": label, "validator_check": "FAIL", "harness_check": "PASS", "reason": str(exc)})
    result = {
        "check": "FAIL" if issues or any(n["harness_check"] == "FAIL" for n in negatives) else "PASS",
        "scope": "independent source/card/owner review; this self-verification is not a second independent scientific reviewer or formal G closure",
        "packet_bytes": len(raw), "packet_sha256": digest(raw),
        "environment": {"python": platform.python_version(), "executable": sys.executable, "purpose": "stdlib Git-material verifier; no product backend"},
        "rows": 35, "bindings": 36, "bundles": 17,
        "deciding_receipts_verified": len(review.receipts), "published_materials_verified": len(review.materials),
        "raw_check_refs": len(packet["raw_receipt_check_registry"]),
        "issues": issues, "negative_controls": negatives,
        "custody_historical_nondeciding": "UNRUN", "P41": "not_established",
        "elapsed_s": time.monotonic() - start,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["check"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
