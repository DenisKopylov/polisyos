from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import pydantic
from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.artifacts import io as ir_io
from polisyos.ir.model_layer.canon import CanonSpec, CanonViolation

class MappingBackedCAS:
    def __init__(self, cas: FileSystemCAS, manifest: dict) -> None:
        self.cas = cas
        self.manifest = manifest
        self.get_manifest_calls = 0
        self.get_bytes_calls = 0

    def get_manifest(self, artifact_id):
        self.get_manifest_calls += 1
        return self.manifest

    def get_bytes(self, artifact_id):
        self.get_bytes_calls += 1
        return self.cas.get_bytes(artifact_id)

def nested_list(depth: int):
    value = 0
    for _ in range(depth):
        value = [value]
    return value

def fail(message: str):
    raise AssertionError(message)

result = {
    "python": sys.version.split()[0],
    "python_executable": sys.executable,
    "pydantic": pydantic.__version__,
    "io_source": str(Path(ir_io.__file__).resolve()),
}
with tempfile.TemporaryDirectory(prefix="can-c4-independent-") as tmp:
    cas = FileSystemCAS(Path(tmp) / "cas")
    payload = nested_list(129)
    ref_data = ir_io.put_json_artifact(
        cas,
        payload,
        kind="c4.mapping.oracle",
        schema_name="c4.mapping.oracle",
        schema_version="1.0",
        canon_spec=CanonSpec(max_depth=129),
    )
    ref = CoreArtifactRef.model_validate(ref_data)
    manifest_model = cas.get_manifest(ref.artifact_id)
    untouched_mapping = manifest_model.model_dump(mode="json")
    original_mapping = copy.deepcopy(untouched_mapping)
    if untouched_mapping["artifact_id"] != str(ref.artifact_id):
        fail("full JSON mapping artifact_id did not match the typed ref")
    if untouched_mapping["canon"]["separators"] != [",", ":"]:
        fail("Pydantic JSON-mode did not expose the expected separators list")
    if untouched_mapping["canon"]["max_depth"] != 129:
        fail("the persisted nondefault depth was not 129")

    wrapper = MappingBackedCAS(cas, untouched_mapping)
    decoded = ir_io.get_json_artifact(wrapper, ref.artifact_id)
    if decoded != payload:
        fail("JSON-mode full Mapping did not round-trip exact payload")
    if wrapper.manifest != original_mapping:
        fail("reader mutated the supplied full JSON-mode manifest")
    if wrapper.get_manifest_calls != 1 or wrapper.get_bytes_calls != 1:
        fail("positive path did not perform exactly one manifest and byte read")
    result["positive"] = {
        "typed_ref": str(ref.artifact_id),
        "manifest_ref": untouched_mapping["artifact_id"],
        "payload_equal": decoded == payload,
        "full_mapping_unchanged": wrapper.manifest == original_mapping,
        "profile_max_depth": untouched_mapping["canon"]["max_depth"],
        "separators_json_value": untouched_mapping["canon"]["separators"],
        "manifest_reads": wrapper.get_manifest_calls,
        "byte_reads": wrapper.get_bytes_calls,
    }

    negative_mutations = {
        "separator_list_len_1": lambda m: m["canon"].update(separators=[":"]),
        "separator_list_len_3": lambda m: m["canon"].update(separators=[",", ":", ";"]),
        "separator_nonstring": lambda m: m["canon"].update(separators=[",", 1]),
        "separator_bool": lambda m: m["canon"].update(separators=[True, ":"]),
        "unsupported_name": lambda m: m["canon"].update(name="polisyos.canon.future"),
        "unsupported_version": lambda m: m["canon"].update(version="0.3.0"),
        "wrong_name_type": lambda m: m["canon"].update(name=1),
        "wrong_version_type": lambda m: m["canon"].update(version=3),
        "wrong_boolean_field_type": lambda m: m["canon"].update(forbid_floats="false"),
        "wrong_forbid_nan_inf_type": lambda m: m["canon"].update(forbid_nan_inf="true"),
        "wrong_exclude_none_type": lambda m: m["canon"].update(exclude_none=0),
        "wrong_sort_keys_type": lambda m: m["canon"].update(sort_keys=1),
        "wrong_ensure_ascii_type": lambda m: m["canon"].update(ensure_ascii="false"),
        "wrong_depth_type": lambda m: m["canon"].update(max_depth="129"),
        "boolean_depth": lambda m: m["canon"].update(max_depth=True),
        "negative_depth": lambda m: m["canon"].update(max_depth=-1),
        "extra_profile_field": lambda m: m["canon"].update(unexpected="value"),
        "missing_separator_field": lambda m: m["canon"].pop("separators"),
        "absent_profile": lambda m: m.update(canon=None),
    }
    negative_results = {}
    for case_name, mutate in negative_mutations.items():
        mutated = copy.deepcopy(original_mapping)
        mutate(mutated)
        negative_wrapper = MappingBackedCAS(cas, mutated)
        try:
            ir_io.get_json_artifact(negative_wrapper, ref.artifact_id)
        except CanonViolation as exc:
            if str(exc) != "unsupported_ir_canon_profile":
                fail(f"{case_name} raised unexpected CanonViolation: {exc}")
        else:
            fail(f"{case_name} unexpectedly passed profile admission")
        if negative_wrapper.get_bytes_calls != 0:
            fail(f"{case_name} reached payload bytes before refusal")
        negative_results[case_name] = {
            "refused": True,
            "byte_reads": negative_wrapper.get_bytes_calls,
        }
    result["negative_profiles"] = negative_results

    module_path = Path(ir_io.__file__)
    candidate_source = module_path.read_text()
    normalization = """        separators = payload.get("separators")
        if (
            type(separators) is list
            and len(separators) == 2
            and all(type(separator) is str for separator in separators)
        ):
            payload["separators"] = tuple(separators)
"""
    if candidate_source.count(normalization) != 1:
        fail("could not isolate exactly one JSON separators normalizer for removal control")
    marker_source = Path("tests/unit/core/artifacts/test_ir_adapter.py").read_text()
    if "test_ir_json_reader_accepts_unmodified_json_mode_manifest_mapping" not in marker_source:
        fail("on-disk positive test marker is missing")
    if "test_ir_json_reader_rejects_malformed_json_mapping_separators_before_bytes" not in marker_source:
        fail("on-disk negative test marker is missing")
    # Execute the exact candidate module source with only the normalizing branch removed.
    # Source, tests, docs, and all test markers on disk remain untouched.
    source_without_normalizer = candidate_source.replace(normalization, "", 1)
    exec(compile(source_without_normalizer, str(module_path), "exec"), ir_io.__dict__)
    removal_wrapper = MappingBackedCAS(cas, original_mapping)
    try:
        ir_io.get_json_artifact(removal_wrapper, ref.artifact_id)
    except CanonViolation as exc:
        removal_error = str(exc)
    else:
        fail("valid JSON Mapping remained green after removing its normalizer")
    if removal_error != "unsupported_ir_canon_profile":
        fail(f"removal control refused for the wrong reason: {removal_error}")
    if removal_wrapper.get_bytes_calls != 0:
        fail("removal-control refusal occurred after a byte read")
    result["remove_property_keep_markers"] = {
        "candidate_mapping_with_normalizer": "passes",
        "normalizer_removed_in_memory": "unsupported_ir_canon_profile",
        "byte_reads_after_removal": removal_wrapper.get_bytes_calls,
        "on_disk_positive_and_negative_test_markers_remain": True,
    }

print(json.dumps(result, sort_keys=True, indent=2))
