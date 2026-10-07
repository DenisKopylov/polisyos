import dataclasses, json, pathlib, tomllib
from tools.ops_runners.release.build_release_notes import structured_compatibility_changes, render_release_notes
from tools.ops_runners.release.check_compatibility_release_gates import _validate_fragments
root=pathlib.Path.cwd()
path=root/'release-fragments/unreleased/2026-10-07-catalog-default-resources.toml'
fragment=tomllib.loads(path.read_text());fragment['__path__']=str(path)
policy=tomllib.loads((root/'architecture/gates/compatibility_release.toml').read_text())
errors,findings=_validate_fragments(root,policy,[fragment],breaking_classes=())
changes=structured_compatibility_changes([fragment])
print(json.dumps({'scope':'one owned fragment + canonical compatibility predicate; no full repository gate verdict','structured_records':changes,'errors':[dataclasses.asdict(x) for x in errors],'findings':[dataclasses.asdict(x) for x in findings]},indent=2))
print(render_release_notes('e02-catalog-resources',[fragment],'2026-10-07'))
assert len(changes)==1 and changes[0]['impact']=='compatible'
assert not errors and not findings

assert changes[0]["change_class"] == "python-public-api"
assert "public_experimental" in changes[0]["surface"]
assert "polisyos.data_forge.read_api.catalog.catalog_default_resource_path" in changes[0]["surface"]
