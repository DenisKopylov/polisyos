"""Read immutable Git artifacts; do not infer program correctness or closure.

Only the standard library and Git are needed. Unreceived raw files and hashes
without a byte locator are reported as limitations, never silently validated.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import io
import json
import posixpath
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

PLAN = "policy-engine/docs/research/e02-cloud-test-plan/"
HANDOFF = PLAN + "implementation-handoffs/D/"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
PATH = re.compile(
    r"[^\s<>;]+\.(?:py|json|jsonl|tsv|txt|log|md|toml|yml|yaml|ini|lock|patch|diff)"
    r"(?:@[^#\s]+)?(?:#[^\s]+)?\Z"
)
REFERENCE_KEYS = {
    "path",
    "source_path",
    "test_path",
    "source_paths",
    "source_refs",
    "log",
    "log_ref",
    "raw_log",
    "artifact",
    "artifacts",
    "output",
    "identity_ref",
    "ledger_ref",
    "changed_paths",
    "ref",
    "map",
    "canonical_bundle_locator",
    "residual_ledger_locator",
    "prior_receipts_preserved",
}


class Git:
    def __init__(self, repository: Path) -> None:
        self.repository = repository
        self.cache: dict[tuple[str, str], bytes | None] = {}

    def run(self, *args: str) -> bytes:
        return subprocess.check_output(  # noqa: S603 -- fixed Git executable, argv only; no shell
            [shutil.which("git") or "/usr/bin/git", "-C", str(self.repository), *args],
            stderr=subprocess.DEVNULL,
        )

    def blob(self, ref: str, path: str) -> bytes | None:
        key = ref, path
        if key not in self.cache:
            try:
                self.cache[key] = self.run("show", f"{ref}:{path}")
            except subprocess.CalledProcessError:
                self.cache[key] = None
        return self.cache[key]

    def paths(self, ref: str) -> list[str]:
        return self.run("ls-tree", "-r", "--name-only", ref).decode().splitlines()


class Verifier:
    def __init__(self, git: Git, target: str, base: str) -> None:
        self.git, self.target, self.base = git, target, base
        self.paths = set(git.paths(target))
        self.counts: collections.Counter[str] = collections.Counter()
        self.errors: list[dict] = []
        self.limits: list[dict] = []
        self.checked: set[tuple] = set()
        self.hashes_seen = 0
        self.hashes_bound = 0
        self.objects_checked: set[str] = set()

    def issue(
        self, kind: str, owner: str, locator: str, detail: str, *, limit: bool = False
    ) -> None:
        item = {"kind": kind, "artifact": owner, "locator": locator, "detail": detail}
        destination = self.limits if limit else self.errors
        if item not in destination:
            destination.append(item)

    def resolve(
        self, value: str, owner: str, pin: str | None = None
    ) -> tuple[str, str, bytes | None, bool]:
        raw = value.split("#", 1)[0]
        if "@" in raw:
            raw, pin = raw.rsplit("@", 1)
        ref = pin or self.target
        external = raw.startswith("/") or raw.startswith("file:") or "raw/" in raw
        if raw.startswith("/"):
            # An imported Python module's archived origin can still identify a
            # Git path. Other absolute paths remain outside this byte census.
            if "/policy-engine/" in raw:
                raw = "policy-engine/" + raw.split("/policy-engine/", 1)[1]
            elif "/src/polisyos/" in raw:
                raw = "policy-engine/src/polisyos/" + raw.split("/src/polisyos/", 1)[1]
        candidates = [raw, posixpath.normpath(posixpath.join(posixpath.dirname(owner), raw))]
        if raw.startswith("received/"):
            candidates.append(PLAN + "results/" + raw)
        if raw.startswith(("src/", "tests/", "tools/", "release-fragments/")):
            candidates.append("policy-engine/" + raw)
        if raw.startswith("polisyos/"):
            candidates.append("policy-engine/src/" + raw)
        if "/" not in raw:
            matches = [
                p for p in self.paths if p.startswith(HANDOFF) and posixpath.basename(p) == raw
            ]
            if len(matches) == 1:
                candidates.extend(matches)
        for path in dict.fromkeys(candidates):
            data = self.git.blob(ref, path)
            if data is not None:
                return ref, path, data, external
        return ref, raw, None, external

    def reference(
        self,
        value: object,
        owner: str,
        locator: str,
        *,
        pin: str | None = None,
        digest: str | None = None,
        size: object = None,
        blob: str | None = None,
    ) -> bool:
        if not isinstance(value, str):
            return False
        ref, path, data, external = self.resolve(value, owner, pin)
        if data is None and not PATH.fullmatch(value):
            return False
        signature = ref, path, digest, size, blob
        if signature in self.checked:
            return True
        self.checked.add(signature)
        self.counts["unique_reference_claims"] += 1
        if data is None:
            self.issue(
                "unavailable_raw_or_external" if external else "missing_git_reference",
                owner,
                locator,
                f"{path}@{ref}",
                limit=external,
            )
            return True
        self.counts["available_reference_claims"] += 1
        if digest is not None:
            actual = hashlib.sha256(data).hexdigest()
            self.counts["sha256_claims_checked"] += 1
            if actual != digest:
                self.issue(
                    "sha256_mismatch",
                    owner,
                    locator,
                    f"{path}@{ref}: declared {digest}; actual {actual}",
                )
        if isinstance(size, int) and not isinstance(size, bool):
            self.counts["size_claims_checked"] += 1
            if len(data) != size:
                self.issue(
                    "size_mismatch",
                    owner,
                    locator,
                    f"{path}@{ref}: declared {size}; actual {len(data)}",
                )
        if blob is not None:
            actual = hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
            ).hexdigest()
            self.counts["git_blob_claims_checked"] += 1
            if actual != blob:
                self.issue(
                    "git_blob_mismatch",
                    owner,
                    locator,
                    f"{path}@{ref}: declared {blob}; actual {actual}",
                )
        return True

    def walk(
        self, value: object, owner: str, locator: str = "$", candidate: str | None = None
    ) -> None:
        if isinstance(value, list):
            for i, item in enumerate(value):
                self.walk(item, owner, f"{locator}[{i}]", candidate)
            return
        if not isinstance(value, dict):
            return
        implementations = value.get("implementation_commits", [])
        local_candidate = (
            value.get("candidate_sha")
            or value.get("deciding_candidate_sha")
            or value.get("target_sha")
            or value.get("implementation_sha")
            or (implementations[-1] if implementations else None)
            or candidate
        )
        pin = value.get("commit") or value.get("source_sha")
        path = value.get("path")
        if isinstance(path, str):
            path_pin = pin or (
                local_candidate
                if path.startswith(("policy-engine/src/", "policy-engine/tests/"))
                else None
            )
            self.reference(
                path,
                owner,
                locator + ".path",
                pin=path_pin,
                size=value.get("bytes"),
                blob=value.get("git_blob"),
            )
        for key, item in value.items():
            loc = locator + "." + key
            object_refs = item if key.endswith("_commits") and isinstance(item, list) else [item]
            if "sha" in key or "commit" in key or key.endswith("_tree"):
                for object_ref in object_refs:
                    if (
                        isinstance(object_ref, str)
                        and HEX40.fullmatch(object_ref)
                        and object_ref not in self.objects_checked
                    ):
                        self.objects_checked.add(object_ref)
                        self.counts["git_object_claims_checked"] += 1
                        try:
                            kind = self.git.run("cat-file", "-t", object_ref).decode().strip()
                            if kind not in {"commit", "tree", "blob"}:
                                self.issue("unexpected_git_object_kind", owner, loc, kind)
                        except subprocess.CalledProcessError:
                            self.issue("unavailable_git_object", owner, loc, object_ref, limit=True)
            if isinstance(item, str) and HEX64.fullmatch(item) and "sha256" in key:
                self.hashes_seen += 1
                stem = key.removesuffix("_sha256") if key != "sha256" else ""
                names = [stem, stem + "_ref", stem + "_path"] if stem else []
                names += ["path", "log", "raw_log", "ref", "output"] if not stem else []
                if stem == "log":
                    names.append("raw_log")
                if stem == "original_module":
                    names = ["modified_module"]
                ref_value = next(
                    (
                        value[n]
                        for n in names
                        if isinstance(value.get(n), str)
                        and (
                            PATH.fullmatch(value[n])
                            or (
                                "\n" not in value[n]
                                and self.resolve(value[n], owner, pin)[2] is not None
                            )
                        )
                    ),
                    None,
                )
                hash_pin = pin
                if stem == "module":
                    hash_pin = hash_pin or local_candidate
                if isinstance(ref_value, str) and ref_value.startswith(
                    ("policy-engine/src/", "policy-engine/tests/")
                ):
                    hash_pin = hash_pin or local_candidate
                if stem == "test":
                    hash_pin = (
                        value.get("test_commit_sha") or value.get("test_sha") or local_candidate
                    )
                if stem == "original_module":
                    hash_pin = value.get("target_sha") or local_candidate
                if ref_value is not None:
                    self.hashes_bound += 1
                    self.reference(
                        ref_value, owner, loc, pin=hash_pin, digest=item, size=value.get("bytes")
                    )
                else:
                    inline = value.get(stem)
                    if isinstance(inline, str) and not PATH.fullmatch(inline):
                        self.hashes_bound += 1
                        self.counts["inline_utf8_sha256_claims_checked"] += 1
                        actual = hashlib.sha256(inline.encode()).hexdigest()
                        if actual != item:
                            self.issue(
                                "inline_sha256_mismatch",
                                owner,
                                loc,
                                f"declared {item}; actual {actual}",
                            )
                    else:
                        self.issue("hash_without_byte_locator", owner, loc, item, limit=True)
            elif isinstance(item, dict) and PATH.fullmatch(key) and "path" not in item:
                self.walk({"path": key, **item}, owner, loc, local_candidate)
                continue
            elif isinstance(item, str) and HEX64.fullmatch(item) and PATH.fullmatch(key):
                self.hashes_seen += 1
                self.hashes_bound += 1
                self.reference(key, owner, loc, pin=local_candidate, digest=item)
            elif (
                isinstance(item, str)
                and HEX64.fullmatch(item)
                and locator.endswith(".imported_source_sha256")
            ):
                self.hashes_seen += 1
                self.hashes_bound += 1
                self.reference(
                    "policy-engine/src/" + key.replace(".", "/") + ".py",
                    owner,
                    loc,
                    pin=candidate,
                    digest=item,
                )
            if key in REFERENCE_KEYS:
                refs = item if isinstance(item, list) else [item]
                for ref_value in refs:
                    self.reference(ref_value, owner, loc, pin=pin)
            if key == "candidate_blob_inputs" and isinstance(item, list):
                for i, entry in enumerate(item):
                    self.reference(
                        entry.get("path"),
                        owner,
                        f"{loc}[{i}]",
                        pin=local_candidate,
                        blob=entry.get("git_blob"),
                    )
                # These are explicitly bound to their owner's candidate, not
                # necessarily the later aggregate tree.
                continue
            self.walk(item, owner, loc, local_candidate)

    def parse(self, path: str) -> object:
        try:
            result = json.loads(self.git.blob(self.target, path))
        except (ValueError, TypeError) as exc:
            self.issue("invalid_json", path, "$", str(exc))
            return None
        self.counts["json_files_parsed"] += 1
        return result

    def rows(self, path: str) -> list[dict[str, str]]:
        return list(
            csv.DictReader(io.StringIO(self.git.blob(self.target, path).decode()), delimiter="\t")
        )

    def census(self) -> dict:
        owners = [
            r
            for r in self.rows(PLAN + "execution-organization/finding-owners.tsv")
            if r["unit"] == "D"
        ]
        bundles = [
            r
            for r in self.rows(PLAN + "execution-organization/bundle-owners.tsv")
            if r["unit"] == "D"
        ]
        ids = {r["finding_id"] for r in owners}
        routes = [r for r in self.rows(PLAN + "results/routes.tsv") if r["finding_id"] in ids]
        cells = {r["id"]: r for r in self.rows(PLAN + "results/cells.tsv")}
        selected = {r["cell_id"] for r in routes}
        missing = selected - cells.keys()
        if missing:
            self.issue("route_without_cell", PLAN + "results/routes.tsv", "$", str(sorted(missing)))
        mapped = self.parse(HANDOFF + "baseline-map.json")
        if mapped:
            for name, actual, declared in [
                ("finding_ids", ids, set(mapped["findings"])),
                ("cell_ids", selected, set(mapped["cells"])),
                (
                    "bundle_ids",
                    {r["bundle_id"] for r in bundles},
                    {b for f in mapped["findings"].values() for b in f["bundle_ids"]},
                ),
            ]:
                if actual != declared:
                    self.issue(
                        "census_mismatch",
                        HANDOFF + "baseline-map.json",
                        name,
                        f"missing={sorted(actual - declared)}; extra={sorted(declared - actual)}",
                    )
            by_finding = collections.defaultdict(set)
            for route in routes:
                by_finding[route["finding_id"]].add(route["cell_id"])
            for owner in owners:
                finding = mapped["findings"].get(owner["finding_id"], {})
                if set(finding.get("candidate_cells", [])) != by_finding[owner["finding_id"]]:
                    self.issue(
                        "finding_route_mismatch",
                        HANDOFF + "baseline-map.json",
                        owner["finding_id"],
                        "complete route cell sets differ",
                    )
                if finding.get("closure_owner") != owner["source_closure_owner"]:
                    self.issue(
                        "finding_owner_mismatch",
                        HANDOFF + "baseline-map.json",
                        owner["finding_id"],
                        "owner differs from canonical row",
                    )
            for cell_id in selected - missing:
                actual, declared = cells[cell_id], mapped["cells"].get(cell_id, {})
                for field, mapped_field in [
                    ("path", "path"),
                    ("job", "job"),
                    ("source_sha", "source_sha"),
                    ("state", "reported_state"),
                ]:
                    if actual[field] != declared.get(mapped_field):
                        self.issue(
                            "cell_mismatch",
                            HANDOFF + "baseline-map.json",
                            cell_id + "." + field,
                            "canonical and map values differ",
                        )
            self.locators(mapped)
        return {
            "finding_owner_rows": len(owners),
            "finding_ids": sorted(ids),
            "bundle_owners": len(bundles),
            "bundle_ids": sorted(r["bundle_id"] for r in bundles),
            "route_rows": len(routes),
            "distinct_primary_cells": len(selected),
            "states": dict(collections.Counter(cells[i]["state"] for i in selected - missing)),
        }

    def locators(self, document: dict) -> None:
        def visit(value: object, locator: str = "$", sources: dict = document["sources"]) -> None:
            if isinstance(value, dict):
                if isinstance(value.get("source"), str) and "lines" in value and "bytes" in value:
                    source = sources.get(value["source"])
                    if source is None:
                        self.issue(
                            "unknown_locator_source",
                            HANDOFF + "baseline-map.json",
                            locator,
                            value["source"],
                        )
                    else:
                        _, _, data, _ = self.resolve(
                            source["path"], HANDOFF + "baseline-map.json", source["commit"]
                        )
                        if data is None:
                            self.issue(
                                "missing_locator_source",
                                HANDOFF + "baseline-map.json",
                                locator,
                                source["path"],
                            )
                        else:
                            lines = data.splitlines(keepends=True)
                            first, last = value["lines"]
                            bounds = [
                                sum(map(len, lines[: first - 1])),
                                sum(map(len, lines[:last])),
                            ]
                            self.counts["byte_line_locators_checked"] += 1
                            if not 1 <= first <= last <= len(lines) or bounds != value["bytes"]:
                                self.issue(
                                    "locator_mismatch",
                                    HANDOFF + "baseline-map.json",
                                    locator,
                                    f"declared={value['bytes']}; actual={bounds}",
                                )
                for key, item in value.items():
                    visit(item, locator + "." + key)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    visit(item, f"{locator}[{i}]")

        visit(document)

    def run(self) -> dict:
        changed = (
            self.git.run("diff", "--name-only", "--diff-filter=AM", self.base, self.target)
            .decode()
            .splitlines()
        )
        handoffs = sorted(p for p in self.paths if p.startswith(HANDOFF) and p.endswith(".json"))
        parsed = {}
        for path in sorted(set(handoffs) | {p for p in changed if p.endswith(".json")}):
            parsed[path] = self.parse(path)
        for path in handoffs:
            if parsed[path] is not None:
                self.walk(parsed[path], path)
        fragments = [p for p in changed if "/release-fragments/" in p and p.endswith(".toml")]
        for path in fragments:
            try:
                tomllib.loads(self.git.blob(self.target, path).decode())
                self.counts["release_fragments_parsed"] += 1
            except (ValueError, UnicodeError) as exc:
                self.issue("invalid_release_fragment", path, "$", str(exc))
        census = self.census()
        return {
            "schema": "e02-independent-git-artifact-verification/v1",
            "target_sha": self.target,
            "target_tree": self.git.run("rev-parse", self.target + "^{tree}").decode().strip(),
            "base_sha": self.base,
            "scope": {
                "tracked_D_json_files": len(handoffs),
                "changed_json_files": sum(p.endswith(".json") for p in changed),
                "changed_release_fragments": len(fragments),
            },
            "census": census,
            "checks": dict(self.counts),
            "sha256_declarations": self.hashes_seen,
            "sha256_declarations_with_byte_locator": self.hashes_bound,
            "errors": self.errors,
            "limitations": self.limits,
            "limitation_counts": dict(collections.Counter(v["kind"] for v in self.limits)),
            "outcome": "FAIL" if self.errors else "PASS",
            "interpretation": (
                "Git byte/reference/census/syntax reconciliation only. No native runtime replay, "
                "closure verdict, authority admission, or unavailable raw-byte verification."
            ),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    git = Git(args.repo)
    target = git.run("rev-parse", args.target + "^{commit}").decode().strip()
    base = git.run("rev-parse", args.base + "^{commit}").decode().strip()
    report = Verifier(git, target, base).run()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    summary = {k: v for k, v in report.items() if k not in {"limitations", "census"}}
    summary["census"] = {k: v for k, v in report["census"].items() if not k.endswith("_ids")}
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
