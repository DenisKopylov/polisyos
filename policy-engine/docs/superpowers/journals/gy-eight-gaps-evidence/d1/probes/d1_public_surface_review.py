import hashlib,json
from tools.devx.architecture import guardrails as g
policies=g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST)
families=g._parse_public_generated_artifact_families(g.DEFAULT_PUBLIC_MANIFEST)
inventory=g.build_public_surface_inventory(policies)
outputs={g.DEFAULT_PUBLIC_JSON:g.render_public_surface_json(inventory,generated_artifact_families=families),g.DEFAULT_PUBLIC_MD:g.render_public_surface_markdown(inventory)}
for path,value in outputs.items():
 actual=path.read_text();print(json.dumps({"path":str(path.relative_to(g.REPO_ROOT)),"current_owner_render_matches":actual==value,"committed_sha256":hashlib.sha256(actual.encode()).hexdigest(),"current_render_sha256":hashlib.sha256(value.encode()).hexdigest()}))
