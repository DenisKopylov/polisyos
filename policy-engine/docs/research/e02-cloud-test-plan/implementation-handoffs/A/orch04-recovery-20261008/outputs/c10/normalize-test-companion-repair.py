import subprocess
from pathlib import Path
root=Path('/workspace/ORCH04-C10')
rel='policy-engine/tests/unit/runtime/quality/test_recursive_generation_cycle_epoch_gate.py'
s=subprocess.check_output(['git','show','03a7c5d5e206f87097a18480dcf6091eb2af3d93:'+rel],cwd=root,text=True)
s=s.replace('from polisyos.core.artifacts.store import FileSystemCAS','from polisyos.core.artifacts import ArtifactStore\nfrom polisyos.core.artifacts.store import FileSystemCAS',1)
s=s.replace('    if first in {"src", "tools", "apps", "ops", "architecture"}:','''    # Executable journals and worker/oracle programs can construct runtime owners.
    # Their directory names do not exempt their calls from the actual census.
    if first in {
        "src", "tools", "apps", "ops", "architecture", "docs", "dev-oracles", "workers"
    }:''',1)
s=s.replace('''    def actual_n5_input_ref(
        observation: object,
    ) -> object:
        assert observation is simulation''','''    def actual_n5_input_ref(
        observation: object,
        *,
        artifact_store: ArtifactStore | None = None,
    ) -> object:
        assert observation is simulation
        assert artifact_store is runtime.store''',1)
s=s.replace('''                    "value_port",
                }
            ),
        ),
        (
            "polisyos.runtime.quality.generation_cycle",''','''                    "value_port",
                    "eval_safety_verifier",
                    "artifact_store",
                    "candidate_simulation_handoff",
                    "candidate_simulation_currentness_resolver",
                }
            ),
        ),
        (
            "polisyos.runtime.quality.generation_cycle",''',1)
s=s.replace('''            frozenset({"repo_root", "promotion_runtime", "epoch_n9_evidence_resolver"}),''','''            frozenset(
                {
                    "repo_root", "promotion_runtime", "epoch_n9_evidence_resolver",
                    "context_provider", "measurement_catalog", "measurement_providers",
                }
            ),''',1)
s=s.replace('''    expected_promotion_calls = {
''','''    expected_promotion_calls = {
        (
            "polisyos.runtime.quality.generation_cycle",
            "src/polisyos/runtime/quality/generation_cycle.py",
            "GenerationCycleController._promote_completed_generation",
            frozenset({"admitted_batch", "problem", "deployment_identity"}),
        ),
''',1)
new='''def test_recursive_constructor_census_scans_executable_source_families() -> None:
    """Executable families retain actual alias resolution and unknown refusal."""

    repo_root = Path(__file__).resolve().parents[4]
    paths, filesystem_paths = _production_python_paths(repo_root)
    assert paths == filesystem_paths
    for relative_path in (
        "docs/superpowers/journals/family_probe.py",
        "dev-oracles/family_probe.py",
        "workers/family/tests/family_probe.py",
    ):
        assert _source_role(relative_path) == "production_capable"
        found, ports, unresolved = _scan_python_source(
            source="""
from polisyos.runtime.quality.generation_cycle import GenerationCycleController as Owner
Alias = Owner
def build():
    return Alias(repo_root=None)
""",
            module="synthetic.executable_family_probe",
            source_path=relative_path,
        )
        assert len(found) == 1
        assert found[0].source_path == relative_path
        assert found[0].target == (
            "polisyos.runtime.quality.generation_cycle.GenerationCycleController"
        )
        assert found[0].keyword_names == frozenset({"repo_root"})
        assert found[0].authority_scope is None
        assert not found[0].has_keyword_expansion
        assert ports == unresolved == ()
    with pytest.raises(AssertionError, match="unclassified Python/stub path"):
        _source_role("unallocated/family_probe.py")


'''
s=s.replace('def test_recursive_constructor_denominator_has_no_unwrapped_n9_call()',new+'def test_recursive_constructor_denominator_has_no_unwrapped_n9_call()',1)
(root/rel).write_text(s)
