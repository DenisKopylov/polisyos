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
REF = "7dc540d08d30bad8cf23744172c253c934dfc77e"
BASE = "bf3b54c3a894d2d9d9bfb0cd13edb13177405f33"
paths = subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    [_resolve_executable("git"), "diff", "--name-only", BASE, REF], cwd=R, text=True
).splitlines()
if not (
    set(paths)
    == {
        "policy-engine/architecture/public_surface/inventory.json",
        "policy-engine/docs/reference/public-surface.md",
        "policy-engine/src/polisyos/foundry/uncertainty/README.md",
    }
):
    raise AssertionError
hashes = {}
for path in paths:
    data = subprocess.check_output([_resolve_executable("git"), "show", REF + ":" + path], cwd=R)  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
    if not ((R / path).read_bytes() == data):
        raise AssertionError
    hashes[path] = hashlib.sha256(data).hexdigest()
for path, generated in [
    ("architecture/public_surface/inventory.json", "inventory.json"),
    ("docs/reference/public-surface.md", "public-surface.md"),
    ("docs/reference/generated-artifacts.md", "generated-artifacts.md"),
]:
    if not ((P / path).read_bytes() == (observed_o / "generated-bf3" / generated).read_bytes()):
        raise AssertionError
data = json.loads((P / "architecture/public_surface/inventory.json").read_text())
readme = (P / "src/polisyos/foundry/uncertainty/README.md").read_text()
release = tomllib.loads(
    (
        P / ("release-fragments/unreleased/2026-10-06-e02-foundry-calibration-reader.toml")
    ).read_text()
)


def entry(x: object, module: object) -> object:
    return next(e for p in x["packages"] for e in p["entrypoints"] if e["module"] == module)


def validate(x: object, doc: object, fragment: object) -> None:
    if not (x == json.loads((observed_o / "generated-bf3/inventory.json").read_text())):
        raise AssertionError
    if not (entry(x, "polisyos.calibration")["export_count"] == 29):
        raise AssertionError
    if not (entry(x, "polisyos.foundry.uncertainty")["export_count"] == 20):
        raise AssertionError
    if "load_foundry_calibration_report" not in entry(x, "polisyos.foundry.uncertainty")["exports"]:
        raise AssertionError
    if not (re.search("Exports: 20 names declared", doc)):
        raise AssertionError
    if not (fragment["surface_classification"] == "public_stable"):
        raise AssertionError


validate(data, readme, release)
controls = []
for label in [
    "stale-uncertainty-count19",
    "omitted-reader-export-count20-retained",
    "fake-lazy-mode",
    "stale-readme-count19",
    "wrong-classification",
]:
    corrupt = copy.deepcopy(data)
    doc = readme
    fragment = copy.deepcopy(release)
    if label == "stale-uncertainty-count19":
        entry(corrupt, "polisyos.foundry.uncertainty")["export_count"] = 19
    elif label == "omitted-reader-export-count20-retained":
        entry(corrupt, "polisyos.foundry.uncertainty")["exports"].remove(
            "load_foundry_calibration_report"
        )
    elif label == "fake-lazy-mode":
        entry(corrupt, "polisyos.foundry.uncertainty")["facade_mode_observed"] = "lazy_facade"
    elif label == "stale-readme-count19":
        doc = doc.replace("Exports: 20 names declared", "Exports: 19 names declared")
    else:
        fragment["surface_classification"] = "public_experimental"
    try:
        validate(corrupt, doc, fragment)
    except AssertionError:
        controls.append({"case": label, "outcome": "REJECTED"})
    else:
        raise AssertionError("corrupt publication property admitted")
for path, h in hashes.items():
    if not (hashlib.sha256((R / path).read_bytes()).hexdigest() == h):
        raise AssertionError
result = {
    "source_sha": BASE,
    "source_tree": "0a414803650c9646b597ba24c93afbea0632dcd1",
    "companion_sha": REF,
    "companion_tree": subprocess.check_output(  # noqa: S603 - admitted utility argv uses no shell; executable/source refs are explicit
        [_resolve_executable("git"), "rev-parse", REF + "^{tree}"], cwd=R, text=True
    ).strip(),
    "exact_footprint": paths,
    "property_paths": hashes,
    "before_after_equal": True,
    "canonical_generator_byte_equal": True,
    "counts": {"Calibration": 29, "Foundry uncertainty": 20},
    "source_Python_unchanged": True,
    "new_reader_release_classification": release["surface_classification"],
    "inventory_reviewed_flag_at_this_candidate": release["public_surface_inventory_reviewed"],
    "flag_followup": (
        "Owner may append true companion after this independent canon"
        "ical confirmation; validate that exact one-line delta separa"
        "tely."
    ),
    "controls": controls,
    "publication_verdict": "GO-bounded-owned-canonical-publication",
    "global_guard": "UNRUN by reviewer; no inherited/global PASS asserted",
    "Core_IR_execute_decisions": "not_ratified/unapplied",
}
(observed_o / "publication-review20.json").write_text(json.dumps(result, indent=2) + "\n")
_write_stdout(json.dumps(result, indent=2))
