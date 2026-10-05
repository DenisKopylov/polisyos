import importlib.util,sys,tempfile,hashlib
from pathlib import Path
import pytest
import polisyos.calibration as facade
p=Path('src/polisyos/calibration/curve.py')
original=p.read_text()
needle='is_well_calibrated=not skipped_interval_set and max_ce <= tolerance,'
assert original.count(needle)==1
modified=original.replace(needle,'is_well_calibrated=max_ce <= tolerance,')
with tempfile.TemporaryDirectory(prefix='pcl-removal-') as d:
 q=Path(d)/'curve.py'
 q.write_text(modified)
 spec=importlib.util.spec_from_file_location('pcl_removed_curve',q)
 module=importlib.util.module_from_spec(spec)
 sys.modules[spec.name]=module
 spec.loader.exec_module(module)
 facade.compute_calibration_curve=module.compute_calibration_curve
 print('mutation=remove completeness guard, preserve evaluation_status/n_comparisons/metric fields')
 print('original_sha256='+hashlib.sha256(original.encode()).hexdigest())
 print('mutated_sha256='+hashlib.sha256(modified.encode()).hexdigest())
 result=pytest.main(['tests/unit/calibration/test_curve.py::test_incomplete_curve_cannot_pass_even_with_zero_measured_error','-q'])
 assert result==1, f'mutation must fail defining-property test, got {result}'
 print('REMOVAL_CONTROL=PASS: both incomplete permutations rejected mutant')
