"""Validate and render only the owned frozen release fragment using canonical readers."""
from pathlib import Path
import json
import tomllib
from tools.ops_runners.release.build_release_notes import load_fragments, render_release_notes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
root = Path.cwd()
name = "2026-10-07-tmle-persisted-consumers.toml"
fragments = [x for x in load_fragments(root / "release-fragments/unreleased") if Path(str(x["__path__"])).name == name]
assert len(fragments) == 1
policy = tomllib.loads((root / "architecture/gates/compatibility_release.toml").read_text())
errors, findings = _validate_fragments(root, policy, fragments, breaking_classes=())
print(json.dumps({"selected_fragments": [str(x["__path__"]) for x in fragments], "errors": [x.as_dict() for x in errors], "findings": [x.as_dict() for x in findings]}, sort_keys=True))
assert not errors
assert not findings
print(render_release_notes("e02-consumer-fixture", fragments, "2026-10-07"))
