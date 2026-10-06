"""Independent common nonzero-preservation delta, with full native input fixtures."""
from pathlib import Path
from fractions import Fraction
import hashlib, json, math, os, subprocess, sys, warnings
import numpy as np
import polisyos.foundry.uncertainty as f
from polisyos.foundry.uncertainty import sampling_admission as c
from polisyos.foundry.uncertainty.monte_carlo import MonteCarloPropagator
from polisyos.ir.analytics.uncertainty import DistributionFamily, IntervalSemantics, PropagationMethod, UncertaintyEnvelope, UncertaintySource

R = Path('/workspace/e02-E-continuation-20261006')
S = R / 'policy-engine/src'
O = Path(__file__).parent
REF = '5cdfe613bf91fffbd578848c9e2f8275edc21ee7'
ACTUAL = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip()
paths = ['policy-engine/src/polisyos/foundry/uncertainty/sampling_admission.py', 'policy-engine/src/polisyos/foundry/uncertainty/__init__.py', 'policy-engine/src/polisyos/foundry/uncertainty/README.md', 'policy-engine/src/polisyos/foundry/uncertainty/monte_carlo.py', 'policy-engine/src/polisyos/foundry/uncertainty/covariance.py']
before = {}
for p in paths:
    expected = subprocess.check_output(['git', 'show', REF+':'+p], cwd=R)
    assert (R/p).read_bytes() == expected
    before[p] = hashlib.sha256(expected).hexdigest()
assert len(f.__all__) == 19
for name in ['admit_empirical_weights', 'empirical_cdf', 'admit_unit_uniform']:
    assert getattr(f, name) is getattr(c, name)
mode = os.environ.get('SUPPORT_REMOVAL_MODE', 'positive')
if mode != 'positive':
    def previous_real_guard(values):
        array = np.asarray(values)
        if array.dtype.kind not in 'biuf' and not (array.dtype.kind == 'O' and all(isinstance(value, numbers.Real) for value in array.flat)):
            raise ValueError('sampling coordinates and masses require real numeric values')
        return np.asarray(array, dtype=np.float64)
    # Function globals remain canonical owner's globals, including numbers and np.
    c._real_float64.__code__ = previous_real_guard.__code__

small = np.longdouble('1e-400')
assert small > 0 and float(small) == 0, 'native platform must represent the positive longdouble fixture'
plan2 = c.BoundedIIDMeanPlan(metric_id='fixture-y', pilot_samples=2)
inlets = [('weights', lambda v: f.admit_empirical_weights(v, len(v))), ('CDF', f.empirical_cdf), ('uniform', f.admit_unit_uniform), ('range', c.admit_float32_range), ('pilot', lambda v: c.frozen_bernstein_budget(v, plan2))]
refusals = []
if mode == 'positive':
    for representation, tiny, dtype in [('longdouble', small, np.longdouble), ('Fraction', Fraction(1, 10**400), object)]:
        for inlet, call in inlets:
            values = np.array([tiny, 1], dtype=dtype)
            assert values[0] > 0 and float(values[0]) == 0
            with warnings.catch_warnings(record=True) as observed:
                warnings.simplefilter('always')
                try:
                    call(values)
                except ValueError as exc:
                    assert 'nonzero sampling support' in str(exc)
                    assert not observed
                    refusals.append({'representation': representation, 'inlet': inlet, 'exception': 'ValueError', 'warnings': 0, 'callback_count': 0})
                else:
                    raise AssertionError(f'nonzero input admitted as zero by {inlet}')
    # Positions are independently enumerated; categories must not disappear before CDF admission.
    for position in range(3):
        values = np.array([.5, .5, .5], dtype=np.longdouble)
        values[position] = small
        try:
            f.admit_empirical_weights(values, 3)
        except ValueError as exc:
            assert 'nonzero sampling support' in str(exc)
            refusals.append({'representation': 'longdouble', 'inlet': 'weights', 'positive_position': position, 'exception': 'ValueError'})
        else:
            raise AssertionError('positive first/interior/last category collapsed')

    # Supported finite-machine dyadic law remains independently known.
    for values in [np.array([1,1,2],np.int64),np.array([1,1,2],np.float32),np.array([1,1,2],np.float64),np.array([Fraction(1),Fraction(1),Fraction(2)],object),np.array([1,1,2],np.longdouble)]:
        weights = f.admit_empirical_weights(values, 3)
        np.testing.assert_array_equal(weights, [.25,.25,.5])
        np.testing.assert_array_equal(f.empirical_cdf(weights), [.25,.5,1.])
    np.testing.assert_array_equal(f.admit_unit_uniform(np.array([0,Fraction(1,2)],object)), [0,.5])
    np.testing.assert_array_equal(c.admit_float32_range([0.,1.]), [0.,1.])

    # Native pre-nominal admission: raw row still represents nonzero support.
    native = []
    for row_kind, row in [('array', np.array([small],np.longdouble)), ('list', [small])]:
        calls = []
        env = UncertaintyEnvelope(point_estimate=0., confidence_interval=(0.,0.), confidence_level=.95, distribution_family=DistributionFamily.NORMAL, source=UncertaintySource.CALIBRATION, propagation_method=PropagationMethod.NONE, interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL, gate_eligible=False, metadata={'std':0., 'covariance_params':['x'], 'covariance_row':row})
        result = MonteCarloPropagator(f.PropagationConfig(mc_n_samples=100,compute_sensitivity=False)).propagate(lambda **p: calls.append(p) or {'y':p['x']}, {'x':0.}, {'x':env}, ['y'])[0]
        assert not calls and result.envelope.distribution_family is DistributionFamily.UNKNOWN and not result.envelope.gate_eligible
        native.append({'raw_covariance_row_kind':row_kind,'callback_count':0,'family':result.envelope.distribution_family.value,'gate_eligible':False,'limitations':'Independent covariance builder also refuses these row representations; this is a positive admission-order witness, not an effective guard-removal control.'})

    # Freeze-N certificate arithmetic is derived independently of the implementation.
    epsilon=.05; m=256; delta_pilot=delta_main=.025
    a=math.sqrt(math.log(4/delta_pilot)/(2*m)); expected_u=min(.25,max(0.,a)); expected_n=math.ceil((2*expected_u+2*epsilon/3)*math.log(2/delta_main)/(epsilon**2))
    observed_u, observed_n = c.frozen_bernstein_budget(np.zeros(m), c.BoundedIIDMeanPlan(metric_id='fixture-y',pilot_samples=m))
    assert observed_u == expected_u and observed_n == expected_n == 408
    modules=[]
    for name,module in sorted(sys.modules.items()):
        if name.startswith('polisyos.') and getattr(module,'__file__',None):
            path=Path(module.__file__).resolve(); assert path.is_relative_to(S)
            rel='policy-engine/src/'+str(path.relative_to(S))
            expected=subprocess.check_output(['git','show',ACTUAL+':'+rel],cwd=R)
            assert path.read_bytes()==expected
            modules.append({'module':name,'path':rel,'sha256':hashlib.sha256(expected).hexdigest()})
    for p,h in before.items(): assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h
    result={'property_source_sha':REF,'property_source_tree':subprocess.check_output(['git','rev-parse',REF+'^{tree}'],cwd=R,text=True).strip(),'actual_import_source_sha':ACTUAL,'property_paths':before,'before_after_equal':True,'refusals':refusals,'native_MC':native,'pilot_oracle':{'U':observed_u,'N':observed_n},'module_origins':modules,'module_origin_count':len(modules),'verdict':'GO-bounded-common-real-domain-and-nonzero-preservation','authority_or_finding_closure':False,'new_Welfare_consumer':'separate frozen consumer review required','law_scope':'Supported real finite-machine representation; no exact arbitrary-real promise. Refusal preserves unsupported positive atoms instead of silent loss.'}
    (O/'nonzero-support-independent-probe.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['property_source_sha','property_source_tree','actual_import_source_sha','before_after_equal','refusals','native_MC','pilot_oracle','module_origin_count','verdict']},indent=2))
elif mode == 'weights':
    observed = f.admit_empirical_weights(np.array([small,1],np.longdouble),2)
    print(json.dumps({'removed_property':'nonzero-preservation only','exports_retained':len(f.__all__),'source_files_unchanged':True,'weights':observed.tolist(),'positive_input':True}),flush=True)
    assert observed[0] > 0, 'present-but-fake canonical helpers erase a positive category'
elif mode == 'pilot':
    u,n = c.frozen_bernstein_budget(np.full(256,small,np.longdouble),c.BoundedIIDMeanPlan(metric_id='fixture-y',pilot_samples=256))
    print(json.dumps({'removed_property':'nonzero-preservation only','exports_retained':len(f.__all__),'source_files_unchanged':True,'pilot_budget':{'U':u,'N':n},'positive_raw_pilot_becomes_all_zero':True}),flush=True)
    raise AssertionError('present-but-fake common guard emitted a certificate for a pilot whose nonzero values were discarded')
else:
    raise AssertionError('unrecognized mode')
