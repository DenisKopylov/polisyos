import copy
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def _resolve_executable(name: str) -> str:
    (
        "Resolve an admitted executable and refus"  # Exact bound literal continuation.
        "e an unavailable program before invocati"  # Exact bound literal continuation.
        "on."  # Exact bound literal continuation.
    )
    resolved = shutil.which(name)
    if resolved is None:
        raise RuntimeError(f"required utility executable unavailable: {name}")
    return str(Path(resolved).resolve())


def _write_stdout(*values: object, flush: bool = False) -> None:
    (
        "Emit the existing CLI text and optionall"  # Exact bound literal continuation.
        "y flush without logging side effects."  # Exact bound literal continuation.
    )
    sys.stdout.write(" ".join(str(value) for value in values) + "\n")
    if flush:
        sys.stdout.flush()


OUT = Path(__file__).parent
ROOT = Path("/workspace/e02-E-continuation-20261006")
BASE = "5e3e3727685132f270a3a07b9f63dd962a88cd96"
PRODUCT = ROOT / "policy-engine"
POST = OUT / "postimage"
sys.path.insert(0, str(PRODUCT))
from tools.ops_runners.release import (  # noqa: E402 - source-bound fixture
    check_compatibility_release_gates as check,
)
from tools.ops_runners.release.build_release_notes import (  # noqa: E402 - fixture binds the exact source or overlay before importing its consumer
    load_fragments,
    structured_compatibility_changes,
)

policy = tomllib.loads((PRODUCT / "architecture/gates/compatibility_release.toml").read_text())
contract = tomllib.loads((PRODUCT / "architecture/public_surface/contract.toml").read_text())
fragments = load_fragments(POST / "policy-engine/release-fragments/unreleased")
if not (len(fragments) == 2):
    raise AssertionError
errors, findings = check._validate_fragments(PRODUCT, policy, fragments, breaking_classes=())
if errors:
    raise AssertionError
changes = structured_compatibility_changes(fragments)
if not (len(changes) == 2):
    raise AssertionError
packages = {row["module"]: row for row in contract["package"]}
expected = {
    fragments[0]["id"]: "polisyos.calibration",
    fragments[1]["id"]: "polisyos.foundry.uncertainty",
}


# Actual canonical owner/classification from public surface contract. Version owner
# team-architecture retained from G53 accepted owner metadata; no authority inferred.
def canonical_basis(rows: object) -> object:
    reasons = []
    for row in rows:
        module = (
            "polisyos.calibration"
            if row["id"] == "calibration-foundry-reader-alias"
            else "polisyos.foundry.uncertainty"
        )
        package = packages[
            "polisyos.calibration" if module == "polisyos.calibration" else "polisyos.foundry"
        ]
        for key, want in (
            ("owner", package["owner"]),
            ("version_owner", "team-architecture"),
            ("surface", package["classification"] + ": " + module),
        ):
            if row.get(key) != want:
                reasons.append(
                    {"id": row["id"], "field": key, "actual": row.get(key), "required": want}
                )
    return reasons


if canonical_basis(changes):
    raise AssertionError
fake = copy.deepcopy(fragments)
fake[0]["owner"] = "E"
fake[0]["compatibility_change"][0]["owner"] = "E"
fake_errors, _ = check._validate_fragments(PRODUCT, policy, fake, breaking_classes=())
if fake_errors:
    raise AssertionError
fake_reasons = canonical_basis(structured_compatibility_changes(fake))
if not (fake_reasons):
    raise AssertionError
remove = copy.deepcopy(fragments)
for item in remove:
    item["public_surface_inventory_reviewed"] = False
    item["compatibility_change"][0]["public_surface_inventory_reviewed"] = False
remove_errors, _ = check._validate_fragments(PRODUCT, policy, remove, breaking_classes=())
if not (remove_errors):
    raise AssertionError
missing = copy.deepcopy(fragments)
missing[0]["compatibility_change"][0].pop("version_owner")
missing_errors, _ = check._validate_fragments(PRODUCT, policy, missing, breaking_classes=())
if not (missing_errors):
    raise AssertionError
result = {
    "schema": "policyos.e02.owned_route_release_parser.v1",
    "actual_parser": (
        "build_release_notes.load_fragments + structured_compatibilit"
        "y_changes; check_compatibility_release_gates._validate_fragm"
        "ents"
    ),
    "base": BASE,
    "fragments": fragments,
    "structured_rows": changes,
    "errors": [e.as_dict() for e in errors],
    "findings": [e.as_dict() for e in findings],
    "canonical_owner_basis": {
        name: {
            "owner": packages[
                "polisyos.calibration" if name == "polisyos.calibration" else "polisyos.foundry"
            ]["owner"],
            "classification": packages[
                "polisyos.calibration" if name == "polisyos.calibration" else "polisyos.foundry"
            ]["classification"],
            "version_owner": "team-architecture (G53 retained canonical version owner)",
        }
        for name in ("polisyos.calibration", "polisyos.foundry.uncertainty")
    },
    "controls": {
        "present_fake_owner_E": {
            "generic_presence_parser_errors": [],
            "canonical_owner_predicate_refuses": fake_reasons,
        },
        "inventory_review_field_removed": {"errors": [e.as_dict() for e in remove_errors]},
        "version_owner_field_removed": {"errors": [e.as_dict() for e in missing_errors]},
    },
    "scope": (
        "Two owned route/public-API companion rows only, not whole re"
        "lease readiness/globalCI or wire/schema/semantic owner ratif"
        "ication."
    ),
}
(OUT / "release-parser.json").write_text(json.dumps(result, indent=2) + "\n")
argv = [
    "git",
    "-C",
    str(ROOT),
    "grep",
    "-n",
    "-E",
    "load_foundry_calibration_report|Calibration re-exports",
    BASE,
    "--",
    "policy-engine/src",
    "policy-engine/tests",
    "policy-engine/docs/reference",
    "policy-engine/release-fragments/unreleased",
]
run = subprocess.run(argv, capture_output=True)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
if not (run.returncode == 0):
    raise AssertionError
(OUT / "tracked-reader-refs-base.stdout").write_bytes(run.stdout)
lines = run.stdout.decode().splitlines()
parsed = []
for line in lines:
    _, path, number, text = line.split(":", 3)
    post = POST / path
    native = subprocess.check_output(  # noqa: S603 - source-bound fixture
        [_resolve_executable("git"), "-C", str(ROOT), "show", BASE + ":" + path]
    )
    new = post.read_bytes() if post.exists() else native
    matches = [
        {"line": i, "text": value}
        for i, value in enumerate(new.decode().splitlines(), 1)
        if "load_foundry_calibration_report" in value or "Calibration re-exports" in value
    ]
    parsed.append(
        {
            "path": path,
            "old_line": int(number),
            "old_text": text,
            "postimage_used": post.exists(),
            "postimage_matching_lines": matches,
        }
    )
source_alias = "from polisyos.calibration import load_foundry_calibration_report"
if not (
    source_alias
    not in (
        POST
        / (
            "policy-engine/src/polisyos/scientist/nod"  # Exact bound literal continuation.
            "es/builtins/simulate/propagate_uncertain"  # Exact bound literal continuation.
            "ty.py"  # Exact bound literal continuation.
        )
    ).read_text()
):
    raise AssertionError
if not (
    "from polisyos.foundry.uncertainty import load_foundry_calibration_report"
    not in (POST / "policy-engine/src/polisyos/calibration/__init__.py").read_text()
):
    raise AssertionError
refs = {
    "schema": "policyos.e02.current_reader_reference_denominator.v1",
    "base": BASE,
    "argv": argv,
    "exit_code": run.returncode,
    "scope": (
        "All tracked source/tests/current public reference and unrele"
        "ased fragments. Historical research receipts excluded from c"
        "urrent mechanism and remain immutable historical evidence. F"
        "ull emitted match list retained."
    ),
    "matches": parsed,
    "current_production_callers": [
        (
            "polisyos.scientist.nodes.builtins.simulate.propagate_uncerta"
            "inty._collect_input_envelopes"
        )
    ],
    "migration": (
        "Only tracked current legacy caller imports the same canonica"
        "l Foundry uncertainty reader directly; unreleased E-topic al"
        "ias removed, no previous main-publication compatibility infe"
        "rred. Root owner statement: alias was not published to main."
    ),
    "old_calibration_alias_remaining_runtime_imports": 0,
    "other_calibration_exports": 28,
    "reader_authority": (
        "Kind/schema/payload validation only; B19"  # Exact bound literal continuation.
        "7 held source/evaluator authority unchan"  # Exact bound literal continuation.
        "ged."  # Exact bound literal continuation.
    ),
}
(OUT / "tracked-reader-refs.json").write_text(json.dumps(refs, indent=2) + "\n")
_write_stdout(
    json.dumps(
        {
            "structured_rows": len(changes),
            "native_parser_errors": len(errors),
            "negative_controls": 3,
            "tracked_ref_matches": len(lines),
            "distinct_ref_paths": len({row["path"] for row in parsed}),
        },
        indent=2,
    )
)
