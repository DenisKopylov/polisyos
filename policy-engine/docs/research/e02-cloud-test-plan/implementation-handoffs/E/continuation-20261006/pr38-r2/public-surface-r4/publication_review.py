"Byte-exact canonical metadata companion review; no global guard assertion."

import copy
import hashlib
import json
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


R = Path("/workspace/e02-E-continuation-20261006")
P = R / "policy-engine"
observed_o = Path(__file__).parent
REF = "2c275dc69a5b544704256ee0ccd37649ae7e8ea4"
BASE = "43c443b6f1015d57cf624598531ef99c22a296e6"
paths = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [_resolve_executable("git"), "diff", "--name-only", BASE, REF], cwd=R, text=True
).splitlines()
expected = {
    "policy-engine/architecture/public_surface/inventory.json",
    "policy-engine/docs/reference/public-surface.md",
    "policy-engine/src/polisyos/foundry/uncertainty/README.md",
    ("policy-engine/release-fragments/unreleased/2026-10-06-e02-calibration-reader-facade.toml"),
    ("policy-engine/release-fragments/unreleased/2026-10-06-e02-finite-law-admission-facade.toml"),
}
if not (set(paths) == expected):
    raise AssertionError
if subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [
        _resolve_executable("git"),
        "diff",
        "--name-only",
        BASE,
        REF,
        "--",
        "policy-engine/src/**/*.py",
    ],
    cwd=R,
    text=True,
).strip():
    raise AssertionError
before = {}
for path in paths:
    content = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + path], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not ((R / path).read_bytes() == content):
        raise AssertionError
    before[path] = hashlib.sha256(content).hexdigest()
for path, generated in [
    ("architecture/public_surface/inventory.json", "inventory.json"),
    ("docs/reference/public-surface.md", "public-surface.md"),
    ("docs/reference/generated-artifacts.md", "generated-artifacts.md"),
]:
    if not ((P / path).read_bytes() == (observed_o / "generated-43c" / generated).read_bytes()):
        raise AssertionError(path)
inventory = json.loads((P / "architecture/public_surface/inventory.json").read_text())
readme = (P / "src/polisyos/foundry/uncertainty/README.md").read_text()
release = {
    n: tomllib.loads((P / ("release-fragments/unreleased/" + n + ".toml")).read_text())
    for n in [
        "2026-10-06-e02-calibration-reader-facade",
        "2026-10-06-e02-finite-law-admission-facade",
    ]
}


def entry(data: object, module: object) -> object:
    return next(e for p in data["packages"] for e in p["entrypoints"] if e["module"] == module)


def validate(data: object, documentation: str, fragments: object) -> None:
    if not (data == json.loads((observed_o / "generated-43c/inventory.json").read_text())):
        raise AssertionError
    if not (entry(data, "polisyos.calibration")["export_count"] == 29):
        raise AssertionError
    if "load_foundry_calibration_report" not in entry(data, "polisyos.calibration")["exports"]:
        raise AssertionError
    if not (entry(data, "polisyos.foundry.uncertainty")["export_count"] == 19):
        raise AssertionError
    if not (re.search(r"Exports: 19 names declared", documentation)):
        raise AssertionError
    for name, classification in [
        ("2026-10-06-e02-calibration-reader-facade", "public_experimental"),
        ("2026-10-06-e02-finite-law-admission-facade", "public_stable"),
    ]:
        if not (fragments[name]["surface_classification"] == classification):
            raise AssertionError
        if fragments[name]["public_surface_inventory_reviewed"] is not True:
            raise AssertionError


validate(inventory, readme, release)
controls = []
for label in [
    "stale-calibration-count",
    "omitted-reader-export-count-retained",
    "fake-lazy-mode",
    "stale-uncertainty-readme-count",
    "false-stable-calibration-classification",
]:
    corrupt = copy.deepcopy(inventory)
    documentation = readme
    fragments = copy.deepcopy(release)
    if label == "stale-calibration-count":
        entry(corrupt, "polisyos.calibration")["export_count"] = 28
    elif label == "omitted-reader-export-count-retained":
        entry(corrupt, "polisyos.calibration")["exports"].remove("load_foundry_calibration_report")
    elif label == "fake-lazy-mode":
        entry(corrupt, "polisyos.foundry.uncertainty")["facade_mode_observed"] = "lazy_facade"
    elif label == "stale-uncertainty-readme-count":
        documentation = readme.replace("Exports: 19 names declared", "Exports: 16 names declared")
    else:
        fragments["2026-10-06-e02-calibration-reader-facade"]["surface_classification"] = (
            "public_stable"
        )
    try:
        validate(corrupt, documentation, fragments)
    except AssertionError:
        controls.append({"case": label, "outcome": "REJECTED"})
    else:
        raise AssertionError("corrupted publication property admitted")
for path, h in before.items():
    if not (hashlib.sha256((R / path).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "companion_sha": REF,
    "companion_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
    ).strip(),
    "source_sha": BASE,
    "footprint": paths,
    "source_python_unchanged": True,
    "canonical_generator_byte_equal": True,
    "counts": {"calibration": 29, "foundry_uncertainty": 19},
    "classification": {
        "calibration": "public_experimental",
        "foundry_uncertainty": "public_stable",
    },
    "property_paths": before,
    "before_after_equal": True,
    "corrupt_field_controls": controls,
    "verdict": "GO-bounded-owned-publication-companion",
    "architecture_limit": (
        "New Cal facade→Foundry report private module edge remains su"
        "bject to separate free E routing fix or precise API owner ad"
        "mission; no global architecture PASS asserted. Core/IR/execu"
        "te owner packets remain unratified."
    ),
    "finding_closure": False,
}
(observed_o / "publication-review-2c275.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
