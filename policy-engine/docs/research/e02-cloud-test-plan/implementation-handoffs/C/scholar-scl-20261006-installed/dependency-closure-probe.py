from __future__ import annotations
import importlib.metadata as md
import json
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

package = md.distribution('policy-engine')
installed = {canonicalize_name(d.metadata['Name']): d.version for d in md.distributions() if d.metadata.get('Name')}
env = default_environment(); env['extra'] = ''
base=[]; missing=[]; mismatched=[]; excluded=[]
for raw in package.requires or []:
    requirement = Requirement(raw)
    if requirement.marker is not None and not requirement.marker.evaluate(env):
        excluded.append(raw)
        continue
    name=canonicalize_name(requirement.name)
    version=installed.get(name)
    row={'requirement':raw,'name':name,'installed_version':version}
    base.append(row)
    if version is None: missing.append(row)
    elif requirement.specifier and not requirement.specifier.contains(version, prereleases=True): mismatched.append(row)
result={'distribution_version':package.version,'base_requires_dist_count':len(base),'base_requirements_satisfied':not missing and not mismatched,'missing_base_requirements':missing,'version_mismatches':mismatched,'requirements_excluded_in_no-extra-evaluation_count':len(excluded),'requirements_excluded_in_no-extra-evaluation':excluded,'installed_distribution_count':len(installed),'pytest_present':'pytest' in installed,'jsonschema_present':'jsonschema' in installed,'optional_extras_selected':[]}
print(json.dumps(result,sort_keys=True))
if not result['base_requirements_satisfied']:
    raise SystemExit(1)
