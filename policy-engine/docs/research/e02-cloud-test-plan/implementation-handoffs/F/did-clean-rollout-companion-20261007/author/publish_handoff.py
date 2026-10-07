"""Package complete unique bounded B204 evidence into the owned Git handoff."""

import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

REPO = Path('/workspace/e02-F-cau-20261006')
SCRATCH = Path('/tmp/e02-F-graph-profile-20261007/cau')
BASE = '25cdea9064ddea2c3a812fd68670076bd4b088cb'
IMPLEMENTATION = 'e1c4bb28c9d5ff936ae1c047619c56cf12ba5347'
PREFIX = 'policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/F/'
SLICE = 'did-clean-rollout-companion-20261007'


def digest(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def gitref(sha, path):
    raw = git('show', sha + ':' + path)
    return {'git_ref': sha, 'path': path, **digest(raw),
            'git_blob': git('rev-parse', sha + ':' + path).decode().strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--independent-review', required=True)
    args = parser.parse_args()
    assert git('rev-parse', 'HEAD').decode().strip() == IMPLEMENTATION
    assert not git('status', '--porcelain=v1').decode()
    manifest = []
    mapping = {}

    def store(source, group='author'):
        source = Path(source)
        raw = source.read_bytes()
        # Lossless compression avoids changing original whitespace or empty streams.
        compress = source.suffix in {'.stdout', '.stderr'} or source.name.endswith(('.stdout.json', '.stderr.txt'))
        name = source.name + ('.gz' if compress else '')
        rel = PREFIX + SLICE + '/' + group + '/' + name
        destination = REPO / rel
        assert not destination.exists()
        destination.parent.mkdir(parents=True, exist_ok=True)
        stored = gzip.compress(raw, mtime=0) if compress else raw
        destination.write_bytes(stored)
        assert (gzip.decompress(stored) if compress else stored) == raw
        record = {'path': rel, **digest(stored), 'encoding': 'gzip' if compress else 'utf-8',
                  'decoded_bytes': len(raw), 'decoded_sha256': hashlib.sha256(raw).hexdigest(),
                  'original_path': str(source), 'group': group}
        manifest.append(record)
        mapping[str(source)] = record
        return record

    # Full raw failures and precommit style correction remain historical observations.
    own_inputs = sorted(p for p in SCRATCH.iterdir() if p.is_file()
                        and p.name != 'publish_handoff.py')
    for path in own_inputs:
        store(path)
    store(Path(__file__))
    independent_dir = Path('/tmp/e02-F-graph-profile-20261007/api-review/combined4ee')
    for name in ['b204.stdout.json', 'b204.stderr.txt', 'b204.execution.json', 'probe_b204.py', 'run_b204.py']:
        store(independent_dir / name, 'independent-api')
    independent_review = store(Path(args.independent_review), 'independent-api')
    native = json.loads((independent_dir / 'b204.stdout.json').read_bytes())
    native_execution = json.loads((independent_dir / 'b204.execution.json').read_bytes())
    measured_sha = native_execution['source_before']['head']
    assert native_execution['exit_code'] == 0
    assert native['checker_positive'] is True and len(native['negative_controls']) == 10
    assert all(control['outcome'] == 'PASS' for control in native['negative_controls'])
    benchmark_path = 'policy-engine/benchmarks/natural_experiments/policy_natural_experiments.py'
    did_path = 'policy-engine/src/polisyos/foundry/methods/catalog/causal/did.py'
    relevant_equalities = []
    for path in [benchmark_path, did_path]:
        left = gitref(IMPLEMENTATION, path)
        right = gitref(measured_sha, path)
        assert left['git_blob'] == right['git_blob'] and left['sha256'] == right['sha256']
        relevant_equalities.append({'implementation': left, 'measured_combined_source': right, 'byte_equal': True})

    def check(stem, outcome, target, scope):
        execution = json.loads((SCRATCH / (stem + '.execution.json')).read_text())
        return {'name': stem, 'command': execution['command'], 'target_sha': target,
                'environment': execution['environment'], 'input_closure': scope,
                'outcome': outcome, 'process_exit_code': execution['exit'],
                'wall_seconds': execution['elapsed_s'],
                'output': mapping[str(SCRATCH / (stem + '.stdout'))]['path'],
                'output_ref': mapping[str(SCRATCH / (stem + '.stdout'))],
                'stderr': mapping[str(SCRATCH / (stem + '.stderr'))]['path'],
                'stderr_ref': mapping[str(SCRATCH / (stem + '.stderr'))],
                'execution_ref': mapping[str(SCRATCH / (stem + '.execution.json'))]}

    checks = [
        check('admission-resume', 'PASS', '4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9', 'Actual exact existing branch/worktree resume admitted with complete verdict; before writes/ordinary fast-forward.'),
        check('importer-check', 'PASS', '4d8eaec43d09d9c7df3a2ac8bd244e4d132d03f9', 'Fresh canonical results importer --check, six unchanged index inputs; not candidate estimator validation.'),
        check('source-clean-rollout-red', 'FAIL', BASE, 'One genuine existing clean_rollout runner/checker; hand four-means ATT agrees. Failure occurs only at old passed diagnostic expectation with two preperiods. No broad inherited-red claim.'),
        check('frozen-format', 'PASS', IMPLEMENTATION, 'Exact complete benchmark source file formatting at frozen candidate; no unrelated edits.'),
        check('frozen-ruff', 'FAIL', IMPLEMENTATION, 'Exact complete benchmark file: two CLI print T201 findings outside changed nested checker. Gate remains FAIL; no suppression/waiver or P41 inherited attribution.'),
        check('base-ruff', 'FAIL', BASE, 'Git exact base source fed to native Ruff via named stdin in unchanged configuration; same two CLI prints. Does not establish full-gate denominator disjointness/P41.'),
        check('source-footprint', 'PASS', IMPLEMENTATION, 'Replace only new nested checker AST by old checker; entire benchmark module then matches base AST. Only one diff path; did.py bytes unchanged.'),
    ]
    checks.append({
        'name': 'independent-native-clean-rollout-and-ten-falsifiers',
        'command': native_execution['argv'], 'target_sha': measured_sha,
        'environment': {**native_execution['env_overrides'], **native['environment']},
        'input_closure': 'One genuine native StandardDiD benchmark fixture; ten diagnostics/ATT output falsifiers retain method/status and reuse real result. Complete origins captured. Benchmark and did defining files byte-equal frozen leaf implementation; not a whole-tree or P41 claim.',
        'outcome': 'PASS', 'process_exit_code': native_execution['exit_code'],
        'wall_seconds': native_execution['wall_seconds'],
        'output': mapping[str(independent_dir / 'b204.stdout.json')]['path'],
        'output_ref': mapping[str(independent_dir / 'b204.stdout.json')],
        'stderr': mapping[str(independent_dir / 'b204.stderr.txt')]['path'],
        'stderr_ref': mapping[str(independent_dir / 'b204.stderr.txt')],
        'execution_ref': mapping[str(independent_dir / 'b204.execution.json')],
        'independent_review_ref': independent_review,
        'counts': {'genuine_case_PASS': 1, 'falsifiers_refused': 10, 'SKIP': 0, 'ERROR': 0},
    })
    checks.append({
        'name': 'ROOT-final-affected-three-case-benchmark',
        'command': ['/workspace/e02-F-closeout-20261006/policy-engine/.venv/bin/python', '-m', 'benchmarks.natural_experiments.policy_natural_experiments', '--mode', 'smoke', '--quiet', '--json', '<ROOT-unique-output-path>'],
        'target_sha': measured_sha,
        'environment': {'PYTHONPATH': 'src:.', 'PYTHONDONTWRITEBYTECODE': '1'},
        'input_closure': 'Complete existing three-case natural-experiments benchmark; ROOT owns once-only final run after independent frozen-source review.',
        'outcome': 'UNRUN', 'output': 'No leaf final benchmark run. Delegated ROOT run/result must be separately source/output-bound; no future PASS or invented output artifact.',
    })
    original_record_path = PREFIX + 'continuation-transfer-20261007/per-ID/B204.json'
    original_record = json.loads(git('show', BASE + ':' + original_record_path))
    receipt = {
        'schema': 'policyos.e02.implementation_handoff.v1', 'unit': 'F', 'slice': SLICE,
        'role': 'finished bounded benchmark checker companion; ROOT owns final benchmark and ledger integration',
        'closure_ids': [], 'related_finding_ids': ['B204'], 'bundle_ids': ['CAU-01'],
        'slice_base_sha': BASE, 'slice_base_tree': git('rev-parse', BASE + '^{tree}').decode().strip(),
        'implementation_commits': [IMPLEMENTATION], 'candidate_sha': IMPLEMENTATION,
        'candidate_tree_sha': git('rev-parse', IMPLEMENTATION + '^{tree}').decode().strip(),
        'branch': 'codex/e02-F-cau-20261006', 'pull_request': None,
        'changed_paths': [benchmark_path],
        'baseline_cells': [],
        'baseline_reason': 'New directly reproduced consumer failure at immutable source25c; existing source-reported cell/card joins remain in original bound per-ID, not rerun or retargeted.',
        'original_criterion_binding': original_record['original_card_refs'],
        'unchanged_original_scientific_recommendation': {
            'check': original_record['check_result'], 'F_outcome': original_record['F_finding_outcome'],
            'carrier': gitref(BASE, original_record_path),
            'scope': 'Original estimator evidence retains prior exact scientific source; no new ATT3/covariance/MC/RDD claim from benchmark companion.',
        },
        'checks': checks,
        'property': {
            'statement': 'The two-pre-period clean-rollout checker accepts the real positive ATT while requiring honest not_testable/insufficient_pre_periods, false passed, absent statistic/p-value and false identification authority.',
            'runtime_path': ['unchanged synthetic panel DGP', 'StandardDifferenceInDifferences.pure_step', 'canonical real CausalEffectReport', 'existing clean_rollout nested checker'],
            'proxy_divergence': 'Old first-diagnostic passed assertion falsely rejected an estimable positive ATT because diagnostic support is insufficient; a passed flag cannot stand in for a testable pretrend or identification.',
            'negative_controls': [control['name'] for control in native['negative_controls']],
            'positive_native_ATT': native['actual_report']['point_estimate'],
            'independent_four_means_ATT': native['independent_four_means_att'],
            'preserved_fixture': native['fixture'],
        },
        'predicate_basis': 'recomputed',
        'capability_state_or_finding_state': 'bounded checker companion GO; existing B204 F recommendation unchanged; final assembled benchmark separate UNRUN until ROOT receipt',
        'authority_purpose': 'known synthetic numerical/diagnostic consumer property only; no real parallel-trends, policy or identification authority',
        'observed_native_environment': native['environment'],
        'python314_optional_backends': 'DoWhy/EconML in-process markers remain excluded; absence is not a backend witness; no dependency/environment changes or shim.',
        'independent_measured_combined_source': {'sha': measured_sha, 'tree': native_execution['source_before']['tree'], 'whole_leaf_tree_not_relabelled': True},
        'defining_file_equalities': relevant_equalities,
        'complete_output_transport': manifest,
        'historical_precommit_style_failures': 'First draft E501 and formatting FAIL corrected before e1 freeze; full original outputs remain author companions. Full native Ruff remains two T201 FAIL.',
        'ROOT_only_read_only_caption_proposal_ref': mapping[str(SCRATCH / 'root-dependent-caption-proposal.json')],
        'ROOT_only_caption_proposal_scope': 'B204 current companion update and B218 limited→bounded-closed supersession advice; no leaf ledger/docs writes or status adoption.',
        'limitations_and_next_owner': [
            'ROOT integrates exact reviewed e1 implementation then performs the affected full three-case benchmark once and binds actual source/stdout/stderr/result.',
            'ATT/design/seed/time_treatment/method params/scoring and diagnostic implementation are unchanged; no new160-panel/4000-RDD wave.',
            'Two-pre support is insufficient for pretrend; not_testable and non-rejection cannot establish real untreated parallel trends.',
            'P41 inherited-red not_established; neither exact base repetition nor file equality supplies full input-denominator disjointness.',
            'No formal G finding closure or code acceptance inferred from F recommendation/independent native GO.',
        ],
    }
    target = REPO / (PREFIX + SLICE + '.json')
    target.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'receipt': str(target), **digest(target.read_bytes()), 'complete_companions': len(manifest), 'decoded_bytes': sum(item['decoded_bytes'] for item in manifest), 'stored_bytes': sum(item['bytes'] for item in manifest)}, indent=2))


if __name__ == '__main__':
    main()
