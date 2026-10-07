"Independent selected release-row review on immutable Git source; no code edits."

from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def _resolve_executable(name: str) -> str:
    "Resolve an admitted executable and refuse an unavailable program before invocation."
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    "Emit the existing CLI text and optionally flush without logging side effects."
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


ROOT = Path("/workspace/e02-E-continuation-20261006")
PRODUCT = ROOT / "policy-engine"
OUT = Path("/workspace/e02-E-pr38-r2-receipts/release-compatibility-G53-independent")
SOURCE = "25ab29c0f527c90f4281a4cf04256acb8f62f051"
BASE = "a2677935015e8a0e7f2dfd5412b671e13fb3175a"
G = "53b309019913b938909d6dc0fc13f8edb409f368"
DDM = "4c5afb1dc10b4e3f4dbc10b50ca6066de9b08ccb"


def _admit_git_object_arguments(arguments: tuple[str, ...]) -> None:
    """Keep object reads from interpreting record refs as Git options.

    Named/abbreviated refs remain available to retired source-pinned replay
    scripts; live packet admissions separately require full immutable SHAs.
    """
    if not arguments or arguments[0] not in {"show", "rev-parse"}:
        return
    safe_information_flags = {"--show-toplevel", "--git-dir", "--git-common-dir"}
    for value in arguments[1:]:
        if not isinstance(value, str) or not value or "\0" in value:
            raise ValueError("Git object argument must be a nonempty string")
        if value.startswith("-"):
            if arguments[0] == "rev-parse" and value in safe_information_flags:
                continue
            raise ValueError("Git object reference must never be an option")
        if ":" in value:
            _, relative = value.split(":", 1)
            path = Path(relative)
            if (
                not path.parts
                or path.is_absolute()
                or ".." in path.parts
                or path.as_posix() != relative
                or "\0" in relative
            ):
                raise ValueError("Git object path must be repository relative")


def git(*args: str) -> bytes:
    _admit_git_object_arguments(args)
    return subprocess.check_output([_resolve_executable("git"), "-C", str(ROOT), *args])  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit


def blob(ref: str, path: str) -> bytes:
    return git("show", ref + ":" + path)


def identity(ref: str, path: str) -> dict:
    data = blob(ref, path)
    return {
        "sha": ref,
        "path": path,
        "blob": git("rev-parse", ref + ":" + path).decode().strip(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


changed = git("diff", "--name-only", BASE, SOURCE).decode().splitlines()
if not (
    len(changed) == 6
    and all(
        p.startswith("policy-engine/release-fragments/unreleased/") and p.endswith(".toml")
        for p in changed
    )
):
    raise AssertionError
if not (git("rev-parse", SOURCE + "^").decode().strip() == BASE):
    raise AssertionError
if not (
    git("rev-parse", SOURCE + "^{tree}").decode().strip()
    == "51343543823afdec2dd86f7e76e1590b1dca0a70"
):
    raise AssertionError

native_paths = [
    "tools/ops_runners/release/check_compatibility_release_gates.py",
    "tools/ops_runners/release/build_release_notes.py",
    "tools/lib/imports.py",
]
for relative in native_paths:
    if not ((PRODUCT / relative).read_bytes() == blob(SOURCE, "policy-engine/" + relative)):
        raise AssertionError

sys.path.insert(0, str(PRODUCT))
native = importlib.import_module("tools.ops_runners.release.check_compatibility_release_gates")
notes = importlib.import_module("tools.ops_runners.release.build_release_notes")
policy_path = "policy-engine/architecture/gates/compatibility_release.toml"
policy = tomllib.loads(blob(SOURCE, policy_path).decode())
contract_path = "policy-engine/architecture/public_surface/contract.toml"
contract = tomllib.loads(blob(SOURCE, contract_path).decode())
if not (blob(SOURCE, contract_path) == blob(BASE, contract_path)):
    raise AssertionError
supported = {}
for package in contract["package"]:
    for name in {package["module"], *package.get("supported_entrypoints", [])}:
        supported[name] = {
            "owner": package["owner"],
            "classification": package["classification"],
            "version_owner": package.get(
                "version_owner", contract["public_surface"]["version_owner"]
            ),
        }
if not (supported["polisyos.calibration"]["owner"] == "team-scientist"):
    raise AssertionError
if not (supported["polisyos.foundry.uncertainty"]["owner"] == "team-polisyos"):
    raise AssertionError
if not (supported["polisyos.ddm"]["owner"] == "team-scientist"):
    raise AssertionError

fixture = OUT / "selected-fragments"
fixture.mkdir(parents=True, exist_ok=True)
for path in changed:
    (fixture / Path(path).name).write_bytes(blob(SOURCE, path))
fragments = notes.load_fragments(fixture)
rows = notes.structured_compatibility_changes(fragments)
errors, findings = native._validate_fragments(PRODUCT, policy, fragments, breaking_classes=())
if not (len(fragments) == len(rows) == 6 and not errors and not findings):
    raise AssertionError


def canonical(fragment: dict) -> None:
    "Resolve row owner/classification/version from tracked contract + G decision."
    changes = fragment.get("compatibility_change", [])
    if not (isinstance(changes, list) and len(changes) == 1):
        raise AssertionError("one owner-scoped structured row is required")
    row = changes[0]
    names = re.findall(r"polisyos\.[A-Za-z0-9_.]+", row["surface"])
    if not (len(names) == 1 and names[0] in supported):
        raise AssertionError("one declared canonical surface is required")
    module = names[0]
    expected = supported[module]
    if not (row["owner"] == expected["owner"]):
        raise AssertionError("structured owner must match canonical contract")
    if not (fragment["owner"] == expected["owner"]):
        raise AssertionError("note owner must match its single canonical surface")
    if not (row["surface"].split(":", 1)[0] == expected["classification"]):
        raise AssertionError("row classification must match canonical contract")
    if not (fragment["surface_classification"].split(":", 1)[0] == expected["classification"]):
        raise AssertionError("note classification must match canonical contract")
    if module == "polisyos.ddm":
        if not (row["change_class"] == fragment["change_class"] == "persisted-artifact-format"):
            raise AssertionError("DDM is a persisted format migration, not a facade API change")
        if not (row["impact"] == "compatible_with_migration"):
            raise AssertionError("DDM version transition has directional reader migration")
        if not (row["version_owner"] == "team-scientist"):
            raise AssertionError("G53 and migration documentation name the DDM registry owner")
        if not (
            row.get("migration_docs")
            == fragment.get("migration_docs")
            == ["src/polisyos/ddm/integration/model_registry_gate.md"]
        ):
            raise AssertionError("DDM migration must bind its canonical reader migration document")
    else:
        if not (row["change_class"] == fragment["change_class"] == "python-public-api"):
            raise AssertionError
        if not (row["impact"] == "additive"):
            raise AssertionError
        if not (row["version_owner"] == expected["version_owner"] == "team-architecture"):
            raise AssertionError
        if fragment.get("public_surface_inventory_reviewed") is not True:
            raise AssertionError
        if row.get("public_surface_inventory_reviewed") is not True:
            raise AssertionError


for fragment in fragments:
    canonical(fragment)

# Complete actual current surface evidence comes from the pinned source, not G53's
# historical 7f 28/19 surface counts. AST literals and committed inventory agree.
inventory_path = "policy-engine/architecture/public_surface/inventory.json"
inventory = json.loads(blob(SOURCE, inventory_path))
if not (blob(SOURCE, inventory_path) == blob(BASE, inventory_path)):
    raise AssertionError
exports = {}
for module, path, expected_count in [
    ("polisyos.calibration", "policy-engine/src/polisyos/calibration/__init__.py", 29),
    (
        "polisyos.foundry.uncertainty",
        "policy-engine/src/polisyos/foundry/uncertainty/__init__.py",
        20,
    ),
    ("polisyos.ddm", "policy-engine/src/polisyos/ddm/__init__.py", 17),
]:
    assignments = [
        n
        for n in ast.walk(ast.parse(blob(SOURCE, path)))
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
    ]
    if not (len(assignments) == 1):
        raise AssertionError
    names = ast.literal_eval(assignments[0].value)
    entry = next(
        e for p in inventory["packages"] for e in p["entrypoints"] if e["module"] == module
    )
    if not (len(names) == expected_count == entry["export_count"]):
        raise AssertionError
    if not (set(names) == set(entry["exports"])):
        raise AssertionError
    if not (blob(SOURCE, path) == blob(BASE, path)):
        raise AssertionError
    exports[module] = {
        "count": expected_count,
        "classification": supported[module]["classification"],
        "canonical_owner": supported[module]["owner"],
        "source": identity(SOURCE, path),
        "exports": names,
        "inventory_mode": entry["facade_mode_observed"],
    }

# Link existence alone is insufficient: bind each referenced source doc/test to
# exact Git bytes and ensure the actual parser's filesystem view sees those bytes.
doc_refs = []
for f in fragments:
    for relative in set(
        f.get("evidence", [])
        + f.get("migration_docs", [])
        + f.get("runbook_docs", [])
        + f["compatibility_change"][0].get("migration_docs", [])
        + f["compatibility_change"][0].get("runbook_docs", [])
    ):
        full = "policy-engine/" + relative
        data = blob(SOURCE, full)
        if not ((PRODUCT / relative).read_bytes() == data):
            raise AssertionError
        doc_refs.append(identity(SOURCE, full))

controls = []
for _i, fragment in enumerate(fragments):
    row = fragment["compatibility_change"][0]
    for field in policy["compatibility_release_gates"]["required_structured_fields"]:
        modified = copy.deepcopy(fragment)
        modified["compatibility_change"][0].pop(field)
        e, _ = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        if not (any(x.message == f"missing `{field}`" for x in e)):
            raise AssertionError
        controls.append(
            {
                "kind": "required-row-field-removal",
                "row_id": row["id"],
                "field": field,
                "actual_generic_parser": [x.as_dict() for x in e],
                "outcome": "REFUSED",
            }
        )
    for location in ["note", "row"]:
        modified = copy.deepcopy(fragment)
        target = modified if location == "note" else modified["compatibility_change"][0]
        target["owner"] = "E"
        e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        if not (not e and not f):
            raise AssertionError(
                "generic parser validates owner presence, not canonical owner identity"
            )
        try:
            canonical(modified)
        except AssertionError as exc:
            reason = str(exc)
        else:
            raise AssertionError("Present but fake E owner was accepted as canonical")
        controls.append(
            {
                "kind": "present-but-fake-canonical-owner",
                "row_id": row["id"],
                "location": location,
                "owner": "E",
                "other_fields_retained": True,
                "actual_generic_parser": "PASS",
                "canonical_owner_predicate": "REFUSED",
                "reason": reason,
            }
        )
    for field, value in [
        ("version_owner", "E"),
        (
            "surface",
            "public_experimental: polisyos.ddm"
            if "polisyos.ddm" in row["surface"]
            else "internal: " + re.findall(r"polisyos\.[A-Za-z0-9_.]+", row["surface"])[0],
        ),
    ]:
        modified = copy.deepcopy(fragment)
        modified["compatibility_change"][0][field] = value
        e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        if not (not e and not f):
            raise AssertionError
        try:
            canonical(modified)
        except AssertionError as exc:
            reason = str(exc)
        else:
            raise AssertionError("Corrupt canonical field was accepted")
        controls.append(
            {
                "kind": "canonical-field-corruption",
                "row_id": row["id"],
                "field": field,
                "value": value,
                "other_fields_retained": True,
                "actual_generic_parser": "PASS",
                "canonical_predicate": "REFUSED",
                "reason": reason,
            }
        )
    modified = copy.deepcopy(fragment)
    modified["compatibility_change"] = []
    e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
    if not (not e and f):
        raise AssertionError
    try:
        canonical(modified)
    except AssertionError as exc:
        reason = str(exc)
    else:
        raise AssertionError("Empty structured carrier accepted as a complete six-row receipt")
    controls.append(
        {
            "kind": "structured-row-carrier-removal",
            "row_id": row["id"],
            "actual_generic_parser": "warning only",
            "canonical_predicate": "REFUSED",
            "reason": reason,
        }
    )

for fragment in fragments:
    row = fragment["compatibility_change"][0]
    if row["change_class"] == "python-public-api":
        modified = copy.deepcopy(fragment)
        modified["public_surface_inventory_reviewed"] = False
        modified["compatibility_change"][0]["public_surface_inventory_reviewed"] = False
        e, _ = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
        if not (any(x.check == "public-surface-review" for x in e)):
            raise AssertionError
        controls.append(
            {
                "kind": "inventory-review-removal",
                "row_id": row["id"],
                "both_fields_removed": True,
                "actual_generic_parser": [x.as_dict() for x in e],
                "outcome": "REFUSED",
            }
        )
    else:
        for field, value in [
            ("impact", "additive"),
            ("change_class", "internal"),
            ("migration_docs", []),
        ]:
            modified = copy.deepcopy(fragment)
            modified["compatibility_change"][0][field] = value
            if field == "migration_docs":
                modified["migration_docs"] = []
            e, f = native._validate_fragments(PRODUCT, policy, [modified], breaking_classes=())
            if not (not e and not f):
                raise AssertionError
            try:
                canonical(modified)
            except AssertionError as exc:
                reason = str(exc)
            else:
                raise AssertionError("DDM migration meaning was erased but accepted")
            controls.append(
                {
                    "kind": "DDM-directional-migration-corruption",
                    "row_id": row["id"],
                    "field": field,
                    "value": value,
                    "other_fields_retained": True,
                    "actual_generic_parser": "PASS",
                    "canonical_G53_profile": "REFUSED",
                    "reason": reason,
                }
            )

ddm_identity = []
for path in [
    "policy-engine/src/polisyos/ddm/integration/model_registry.py",
    ("policy-engine/src/polisyos/ddm/integration/model_registry_record.schema.json"),
    ("policy-engine/src/polisyos/ddm/integration/model_registry_record.v1.schema.json"),
    "policy-engine/src/polisyos/ddm/__init__.py",
    "policy-engine/tests/unit/ddm/test_registry_schema_compatibility.py",
]:
    if not (blob(DDM, path) == blob(SOURCE, path)):
        raise AssertionError
    ddm_identity.append(
        {"old": identity(DDM, path), "current": identity(SOURCE, path), "identical": True}
    )
ddm_review_path = Path("/workspace/e02-E-pr38-r2-receipts/independent-doe-reviewer/review.json")
ddm_bytes = ddm_review_path.read_bytes()
if not (
    hashlib.sha256(ddm_bytes).hexdigest()
    == "032c1beef8ba54e2042926439852a13895c83d569c41dce7f5f2064edea314ec"
):
    raise AssertionError
ddm_review = json.loads(ddm_bytes)["families"]["ddm"]
if not (
    ddm_review["implementation_sha"] == DDM and ddm_review["code_verdict"] == "GO_bounded_mechanism"
):
    raise AssertionError

result = {
    "schema": "e02.E.selected-compatibility-metadata-review.v1",
    "source_sha": SOURCE,
    "source_tree": git("rev-parse", SOURCE + "^{tree}").decode().strip(),
    "base_sha": BASE,
    "G_owner_decision_sha": G,
    "G_owner_decision": identity(
        G,
        (
            "policy-engine/docs/research/e02-cloud-test-plan/integration/"
            "reviews/E-r2-owner-actions-2026-10-06.md"
        ),
    ),
    "reviewer": "independent backtest_r3 leaf; metadata only, no BKT/Welfare code review",
    "footprint": changed,
    "code_schema_test_inventory_contract_changes": [],
    "actual_native_parser": (
        "tools.ops_runners.release.check_compatibility_release_gates."
        "_validate_fragments + build_release_notes.load_fragments/str"
        "uctured_compatibility_changes"
    ),
    "native_parser_source": [identity(SOURCE, "policy-engine/" + p) for p in native_paths],
    "canonical_owner_basis": {
        "contract": identity(SOURCE, contract_path),
        "public_version_owner": contract["public_surface"]["version_owner"],
        "selected_packages": {k: supported[k] for k in exports},
        "DDM_persisted_version_owner": (
            "team-scientist per explicit G53 owner decision and canonical migration doc"
        ),
    },
    "selected_fragment_count": len(fragments),
    "structured_rows": rows,
    "actual_native_errors": [],
    "actual_native_findings": [],
    "fragment_source": [identity(SOURCE, p) for p in changed],
    "current_exports": exports,
    "historical_G53_counts": (
        "G53 7f calibration28/uncertainty19 source is historical; cur"
        "rent pinned source29/20 is verified against exact unchanged "
        "inventory"
    ),
    "docs_and_evidence_refs": doc_refs,
    "negative_controls": controls,
    "DDM_unchanged_source_reuse": {
        "source": DDM,
        "independent_receipt_path": str(ddm_review_path),
        "independent_receipt_sha256": hashlib.sha256(ddm_bytes).hexdigest(),
        "code_verdict": ddm_review["code_verdict"],
        "original_suite": ddm_review["suite"],
        "property_identities": ddm_identity,
        "new_DDM_code_review_performed": False,
        "authority": (
            "Library consistency only; no current feed/time/institutional"
            " signoff/served deployment or LA054/055/056 closure"
        ),
    },
    "environment": {
        "python_executable": sys.executable,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cwd": str(PRODUCT),
        "new_environment": False,
        "new_worktree": False,
        "caps_added": False,
        "production_data_used": False,
    },
    "verdict": "GO-bounded-canonical-owner-release-metadata",
    "limits": [
        (
            "Selected six-row parser and canonical-owner reconciliation o"
            "nly; no generic/global CI PASS"
        ),
        "No code/schema API semantics changed in this metadata delta",
        ("Structured parser presence checks alone do not establish canonical ownership"),
        (
            "Current29/20 reconciliation is reused from independent r5 an"
            "d verified from pinned source/inventory, no dynamic numerica"
            "l family rerun"
        ),
        (
            "DDM17 internal facade and independently reviewed v1/v2 code "
            "are unchanged; deployment/version rollout and current-feed/s"
            "ignoff owner decisions remain separate"
        ),
        "B197/B194/B201/B202 and remaining finding ledger statuses are unchanged",
    ],
}
(OUT / "review.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
_write_stdout(
    json.dumps(
        {
            "verdict": result["verdict"],
            "source": SOURCE,
            "fragments": len(fragments),
            "structured_rows": len(rows),
            "canonical_counts": {k: v["count"] for k, v in exports.items()},
            "controls": len(controls),
            "present_fake_E_owner_generic_PASS_canonical_REFUSED": sum(
                x["kind"] == "present-but-fake-canonical-owner" for x in controls
            ),
            "output": str(OUT / "review.json"),
        }
    )
)
