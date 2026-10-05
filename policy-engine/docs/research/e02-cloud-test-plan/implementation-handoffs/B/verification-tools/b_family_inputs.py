"""Read immutable B family receipts without changing any Git checkout."""

import argparse
import csv
import io
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RECEIPT_ROOT = "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/B"
ORG_ROOT = "policy-engine/docs/research/e02-cloud-test-plan/execution-organization"
FAMILIES = {
    "run": "run.json",
    "exe": "exe-state.json",
    "cas": "cas-tenant-contract.json",
    "dur": "dur-ledger.json",
    "cmp": "cmp-res.json",
    "adapters": "adapters.json",
}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True,
                                   stderr=subprocess.PIPE)


def resolve(value):
    if not re.fullmatch(r"[A-Za-z0-9_./-]+", value) or value.startswith("-"):
        raise ValueError(f"Invalid Git ref: {value!r}")
    return git("rev-parse", "--verify", value + "^{commit}").strip()


def read(sha, path):
    return git("show", f"{sha}:{path}")


def read_json(sha, path):
    return json.loads(read(sha, path))


def blob(sha, path):
    return git("rev-parse", "--verify", f"{sha}:{path}").strip()


def arguments(description):
    global ROOT
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--final-head", required=True)
    parser.add_argument("--family-head", action="append", required=True,
                        metavar="FAMILY=SHA_OR_REF")
    parser.add_argument("--overlay", action="append", default=[],
                        metavar="FAMILY=RECEIPT_PATH",
                        help="Explicit ordered per-finding receipt overlays; each reads at its exact family head")
    parser.add_argument("--source-point", action="append", default=[],
                        metavar="FAMILY=SHA_OR_REF",
                        help="Final receipt's exact source point, for candidate per-file identity comparison")
    parser.add_argument("--require-ready", action="store_true",
                        help="Cohort driver returns nonzero unless every final source binding is ready")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ROOT = args.repo.resolve()
    heads = {}
    for pair in args.family_head:
        name, separator, value = pair.partition("=")
        if not separator or name not in FAMILIES or name in heads:
            parser.error(f"Unknown/duplicate family binding: {pair}")
        heads[name] = resolve(value)
    if set(heads) != set(FAMILIES):
        parser.error("Exactly six family heads required: " + ", ".join(FAMILIES))
    overlays = {family: [] for family in FAMILIES}
    for pair in args.overlay:
        family, separator, path = pair.partition("=")
        if (not separator or family not in FAMILIES or
                not path.startswith(RECEIPT_ROOT + "/") or not path.endswith(".json") or
                ".." in Path(path).parts or not re.fullmatch(r"[A-Za-z0-9_./-]+", path)):
            parser.error(f"Invalid overlay binding: {pair}")
        if path == f"{RECEIPT_ROOT}/{FAMILIES[family]}" or path in overlays[family]:
            parser.error(f"Duplicate base/overlay receipt: {pair}")
        overlays[family].append(path)
    args.overlays = overlays
    source_points = {}
    for pair in args.source_point:
        family, separator, ref = pair.partition("=")
        if not separator or family not in FAMILIES or family in source_points:
            parser.error(f"Invalid/duplicate source point: {pair}")
        source_points[family] = resolve(ref)
    args.source_points = source_points
    return args, resolve(args.final_head), heads


def receipt(heads, family):
    path = f"{RECEIPT_ROOT}/{FAMILIES[family]}"
    return path, read_json(heads[family], path)


def ordered_receipts(args, heads, family):
    base_path, base = receipt(heads, family)
    return [(base_path, base), *[(path, read_json(heads[family], path))
                                for path in args.overlays[family]]]


def declared_source_points(doc):
    """Retain exact explicit source identity fields; do not invent a latest source point."""
    return {key: value for key, value in doc.items()
            if key in {"candidate_sha", "candidate_tree_sha", "implementation_commits",
                       "target_sha", "source_sha", "source_commit", "tested_commit",
                       "implementation_commit", "implementation_tree", "source_freeze"}}


def receipt_source_commit_ids(doc):
    def sha_values(value):
        if isinstance(value, str):
            return {value} if re.fullmatch(r"[0-9a-f]{40}", value) else set()
        if isinstance(value, list):
            return set().union(*(sha_values(item) for item in value))
        if isinstance(value, dict):
            return set().union(*(sha_values(item) for item in value.values()))
        return set()
    # Tree identities are deliberately excluded from accepted source commit pins.
    identities = declared_source_points(doc)
    identities.pop("candidate_tree_sha", None)
    identities.pop("implementation_tree", None)
    commits = sha_values(identities)
    commits.update(check["target_sha"] for check in doc.get("checks", [])
                   if isinstance(check.get("target_sha"), str))
    local = doc.get("local_g_candidate", {})
    if isinstance(local, dict) and isinstance(local.get("sha"), str):
        commits.add(local["sha"])
    return commits


def owner_tables(final):
    def rows(name):
        return list(csv.DictReader(io.StringIO(read(final, f"{ORG_ROOT}/{name}.tsv")),
                                   delimiter="\t"))
    return rows("bundle-owners"), rows("finding-owners")


def disposition_rows(doc):
    value = doc.get("finding_classification", doc.get("finding_dispositions"))
    if isinstance(value, list):
        return [(row.get("finding_id", row.get("id")), index, row)
                for index, row in enumerate(value)]
    if isinstance(value, dict):
        return [(key, key, row) for key, row in value.items()]
    raise ValueError("Receipt has no complete per-finding disposition collection")


def whole_test_paths(command):
    tokens = command if isinstance(command, list) else [str(command)]
    return sorted({match.group(1)
                   for token in tokens
                   for match in re.finditer(r"(?:policy-engine/)?(tests/[A-Za-z0-9_./-]+\.py)",
                                            str(token))})


def write_output(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
