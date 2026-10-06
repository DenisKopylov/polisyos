from pathlib import Path
import json,hashlib
from tools.quality.diagnostics import gen_schema as generator
from tools.quality.diagnostics import generate_ir_reference_catalog as docs
OUT=Path(__file__).parent
assert Path(generator.__file__).is_relative_to(Path("/workspace/e02-F-tmle-20261006/policy-engine"))
assert Path(docs.__file__).is_relative_to(Path("/workspace/e02-F-tmle-20261006/policy-engine"))
original={"ir":str(docs.IR_REFERENCE_PATH),"schemas":str(docs.SCHEMA_REFERENCE_PATH)}
docs.IR_REFERENCE_PATH=OUT/"generated-candidate/docs/reference/ir/schema-catalog.md"
docs.SCHEMA_REFERENCE_PATH=OUT/"generated-candidate/docs/reference/schemas.md"
for path in (docs.IR_REFERENCE_PATH,docs.SCHEMA_REFERENCE_PATH):path.parent.mkdir(parents=True,exist_ok=True)
print(json.dumps({"canonical_generator":generator.__file__,"canonical_docs_generator":docs.__file__,"destination_only_redirect":original,"actual_destinations":[str(docs.IR_REFERENCE_PATH),str(docs.SCHEMA_REFERENCE_PATH)]}),flush=True)
raise SystemExit(generator.main(["--models","ir","--output-dir",str(OUT/"generated-candidate/schemas"),"--cache-dir",str(OUT/"candidate-generator-cache")]))
