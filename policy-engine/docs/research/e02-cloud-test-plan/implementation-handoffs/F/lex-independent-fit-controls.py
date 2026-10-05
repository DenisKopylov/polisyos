from __future__ import annotations

import argparse
import ast
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import tempfile
import textwrap

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import from_canonical_bytes
from polisyos.ir.loading.norm_pack import NormPack, NormRule, RuleType
from polisyos.lex import NormImpactAnalyzer as RootAnalyzer
from polisyos.lex.legal_evaluation import impact_diff as canonical
from polisyos.lex.normpack.diff import NormDiff
from polisyos.lex.simulator import NormImpactAnalyzer as SimulatorAnalyzer
from polisyos.lex.simulator.cli import render_impact_markdown
from polisyos.runtime.quality.authority import authority_surface_decision

parser = argparse.ArgumentParser()
parser.add_argument('--remove-freeze', action='store_true')
args = parser.parse_args()
repo = Path.cwd().parent
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
assert sha == '56aa7d47876b29956676ef8dc9f04b64c865948f', sha
source = Path(inspect.getfile(canonical.NormImpactAnalyzer)).resolve()
assert source == repo / 'policy-engine/src/polisyos/lex/legal_evaluation/impact_diff.py', source
original_init = canonical.NormImpactAnalyzer.__init__
if args.remove_freeze:
    original_text = textwrap.dedent(inspect.getsource(original_init))
    assert original_text.count('else tuple(passes)') == 1
    namespace = dict(vars(canonical))
    exec(compile(original_text.replace('else tuple(passes)', 'else passes'), str(source) + ':removed-freeze', 'exec'), namespace)
    canonical.NormImpactAnalyzer.__init__ = namespace['__init__']

checks = []
last_payload = None

def pack(name, threshold):
    return NormPack(pack_id=name, jurisdiction='ua', norms=[NormRule(norm_id='n.income', description='Income floor', rule_type=RuleType.OBLIGATION, backend_refs=['expr_ast'], backend_metadata={'must': f'income >= {threshold}'})])

old, new = pack('pack.old', 1), pack('pack.new', 3)

def analyze(cas, analyzer, expected, blockers):
    global last_payload
    result = analyzer.analyze(old, new, context={'income': 2}, decision_packet_ref='decision.independent-fit')
    assert result.cas_artifact_id is not None
    payload = from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(result.cas_artifact_id)))
    last_payload = payload
    persisted = canonical.NormImpactReport.model_validate(payload)
    assert persisted.new_blockers == blockers, (persisted.new_blockers, blockers)
    assert persisted.passes_executed == expected, (persisted.passes_executed, expected)
    assert persisted.resolved_blockers == 0
    assert persisted.norms_modified == 1
    assert persisted.cas_artifact_id is None
    assert persisted.decision_packet_ref == 'decision.independent-fit'
    diff = NormDiff.model_validate(from_canonical_bytes(cas.get_bytes(ArtifactID.model_validate(persisted.norm_diff_ref))))
    assert diff.modified_count == 1 and diff.affected_norm_ids == ['n.income']
    assert authority_surface_decision(payload, surface='lex_impact').blocking is True
    assert 'Candidate Impact Topics' in render_impact_markdown(persisted)
    if blockers:
        assert len(persisted.compliance_deltas) == 1
        assert persisted.compliance_deltas[0].new_issue.code == 'n.income'
        assert persisted.affected_kpis[0].estimated_direction == 'unknown'
    else:
        assert persisted.compliance_deltas == []
    return payload

with tempfile.TemporaryDirectory(prefix='lex-fit-independent-') as temporary:
    root = Path(temporary)
    counter = 0
    def check(name, run):
        global counter, last_payload
        last_payload = None
        counter += 1
        cas = FileSystemCAS(root / str(counter))
        try:
            result = run(cas)
            checks.append({'name': name, 'status': 'PASS', 'persisted_payload': result})
        except Exception as exc:
            checks.append({'name': name, 'status': 'FAIL', 'exception': type(exc).__name__, 'message': str(exc), 'persisted_payload': last_payload})

    def tuple_control(cas):
        assert RootAnalyzer is canonical.NormImpactAnalyzer is SimulatorAnalyzer
        return analyze(cas, RootAnalyzer(cas, passes=('legal',), legal_backend='expr_ast'), ['legal'], 1)
    check('tuple-plan-and-public-alias-native-consumer-control', tuple_control)

    def append_unknown(cas):
        requested = ['legal']
        analyzer = canonical.NormImpactAnalyzer(cas, passes=requested, legal_backend='expr_ast')
        requested.append('legla')
        actual = analyze(cas, analyzer, ['legal'], 1)
        control = analyze(cas, canonical.NormImpactAnalyzer(cas, passes=('legal',), legal_backend='expr_ast'), ['legal'], 1)
        assert actual == control
        return actual
    check('admitted-list-append-unknown-cannot-change-dispatch-or-cas-bytes', append_unknown)

    def replace_plan(cas):
        requested = ['legal']
        analyzer = canonical.NormImpactAnalyzer(cas, passes=requested, legal_backend='expr_ast')
        requested[:] = ['safety']
        return analyze(cas, analyzer, ['legal'], 1)
    check('admitted-list-replacement-cannot-drop-real-legal-transition', replace_plan)

    def clear_plan(cas):
        requested = ['legal']
        analyzer = canonical.NormImpactAnalyzer(cas, passes=requested, legal_backend='expr_ast')
        requested.clear()
        return analyze(cas, analyzer, ['legal'], 1)
    check('admitted-list-clear-cannot-drop-real-legal-transition', clear_plan)

    def empty_plan(cas):
        requested = []
        analyzer = canonical.NormImpactAnalyzer(cas, passes=requested, legal_backend='expr_ast')
        requested.append('legal')
        return analyze(cas, analyzer, [], 0)
    check('explicit-empty-list-cannot-acquire-later-legal-pass', empty_plan)

    def ordered_plan(cas):
        requested = ['safety', 'legal']
        analyzer = canonical.NormImpactAnalyzer(cas, passes=requested, legal_backend='expr_ast')
        requested.reverse()
        actual = analyze(cas, analyzer, ['safety', 'legal'], 1)
        control = analyze(cas, canonical.NormImpactAnalyzer(cas, passes=('safety', 'legal'), legal_backend='expr_ast'), ['safety', 'legal'], 1)
        assert actual == control
        return actual
    check('admitted-two-pass-order-native-payload-matches-tuple-control', ordered_plan)

    def generator_plan(cas):
        requested = (value for value in ['legal'])
        return analyze(cas, canonical.NormImpactAnalyzer(cas, passes=requested, legal_backend='expr_ast'), ['legal'], 1)
    check('accepted-single-use-iterable-is-not-consumed-by-validation', generator_plan)

    def none_plan(cas):
        return analyze(cas, canonical.NormImpactAnalyzer(cas, legal_backend='expr_ast'), ['legal', 'safety'], 1)
    check('none-retains-default-native-legal-and-safety-control', none_plan)

    def reject_unknown(cas):
        try:
            canonical.NormImpactAnalyzer(cas, passes=['legal', 'legla'], legal_backend='expr_ast')
        except ValueError as exc:
            assert 'Unsupported impact pass' in str(exc)
        else:
            raise AssertionError('Unsupported pass accepted')
        return {'admission': 'rejected-before-analyze'}
    check('unknown-at-admission-remains-rejected-control', reject_unknown)

canonical.NormImpactAnalyzer.__init__ = original_init
receipt = {
    'source_sha': sha,
    'source_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=repo, text=True).strip(),
    'source_path': str(source),
    'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'source_file_bytes': source.stat().st_size,
    'mode': 'removed-freeze' if args.remove_freeze else 'frozen-candidate',
    'backend': 'native expr_ast; actual LegalPass/SafetyPass/CAS/readback/render/authority gate',
    'input': 'synthetic two NormPack obligations income>=1 versus income>=3, context income=2; no real law corpus or authority closure',
    'checks': checks,
    'passed': sum(c['status'] == 'PASS' for c in checks),
    'failed': sum(c['status'] == 'FAIL' for c in checks),
    'skipped': 0,
    'errors': 0,
}
print(json.dumps(receipt, ensure_ascii=False, indent=2))
raise SystemExit(1 if receipt['failed'] else 0)
