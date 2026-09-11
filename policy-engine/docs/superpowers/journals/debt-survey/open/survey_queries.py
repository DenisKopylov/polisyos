"""Bounded read-only measurements; no authority or repository changes."""
import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import inspect_tree as census


def vocabularies():
    paths = [p for p in census.source_paths() if p.startswith("src/")]
    terms = ("estimand", "normative", "write_operation", "assurance_level")
    rows = {term: [] for term in terms}
    definitions = {term: [] for term in terms}
    for path in paths:
        source = (census.ROOT/path).read_text()
        tree = ast.parse(source)
        for term in terms:
            if term in source.lower():
                rows[term].append(path)
            for n in ast.walk(tree):
                if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and term in n.name.lower():
                    definitions[term].append({"path":path,"line":n.lineno,"name":n.name,"kind":type(n).__name__})
    cross = json.loads((census.ROOT/"docs/reference/canonical-vocabulary-crosswalk.v1.json").read_text())
    owner = json.loads((census.ROOT/"src/polisyos/fabric/evidence/ceiling_vocabulary.json").read_text())
    return {"base":census.BASE,"denominator":paths,"count":len(paths),
            "independent_enumerations":"pinned tree equals filesystem walk",
            "text_occurrences_include_prose_and_are_not_vocabulary_proof":True,
            "terms":{t:{"file_count":len(rows[t]),"paths":rows[t],
              "distribution":dict(sorted(Counter(p.split('/')[2] for p in rows[t]).items())),
              "ast_definitions":definitions[t]} for t in terms},
            "rulings":cross["ceiling_vocabulary_rulings"],"comparison_registry":owner}


def lex_schema():
    from polisyos.lex.knowledge import store as owner
    from polisyos.runtime.quality.substrate_registry import DEFAULT_L3_LEX_KG_PATH
    path=census.ROOT/DEFAULT_L3_LEX_KG_PATH
    store=owner.LegalKnowledgeStore(path,path.parent)
    try:
        described=store._con.execute("DESCRIBE lex_provisions").fetchall()
        pragma=store._con.execute("PRAGMA table_info('lex_provisions')").fetchall()
        assert [r[0] for r in described]==[r[1] for r in pragma]
        member=store._con.execute("SELECT doc_id, anchor_path FROM lex_provisions WHERE doc_id IS NOT NULL AND anchor_path IS NOT NULL LIMIT 1").fetchone()
        outcome={}
        try:
            result=store.load_provisions_by_anchor(member[0],[member[1]])
            outcome={"returned":len(result)}
        except Exception as exc:
            outcome={"exception_type":type(exc).__name__,"message":str(exc)}
        return {"base":census.BASE,"source":owner.__file__,"database":str(path.resolve()),
                "database_is_external_not_base_bound":True,"read_only":True,
                "column_denominator":described,"column_count":len(described),
                "describe_pragma_identities_equal":True,"one_probe_member":member,
                "actual_method_result":outcome}
    finally:
        store.close()


def ukraine():
    path="src/polisyos/foundry/data_plane/bindings.py"
    tree=ast.parse((census.ROOT/path).read_text())
    fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=="load_ukraine_foundry_intake")
    assignments=[n for n in ast.walk(fn) if isinstance(n,(ast.Assign,ast.AnnAssign))]
    specs=next(n.value for n in assignments if (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="contract_specs" for t in n.targets)) or (isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=="contract_specs"))
    keys=[ast.literal_eval(n.elts[0]) for n in specs.elts]
    # Independent enumeration reads the executable owner's test assertion set.
    test_path="tests/unit/foundry/data_plane/test_bindings_multiscale.py"
    test=ast.parse((census.ROOT/test_path).read_text())
    sets=[{e.value for e in n.elts if isinstance(e,ast.Constant) and isinstance(e.value,str)} for n in ast.walk(test) if isinstance(n,ast.Set)]
    witness=next(s for s in sets if set(keys)==s)
    return {"base":census.BASE,"source":path,"keys":keys,"count":len(keys),
            "independent_test_assertion_set":sorted(witness),"identity_equal":set(keys)==witness,
            "test_source":test_path,"scope":"produced contract keys, not proven runtime consumers"}


def authority():
    path="docs/system-design-decisions/policyos-identity-and-custody-boundary.md"
    text=(census.ROOT/path).read_text()
    lines=text.splitlines()
    return {"base":census.BASE,"path":path,"frontmatter":text.split("---",2)[1],
        "operational_boundary":[{"line":i,"text":s} for i,s in enumerate(lines,1)
         if re.search("mint|GY-O0|jurisdiction_specific|four-way|§5",s,re.I)]}


def invocation():
    path=Path(__file__).parent/"raw/invocation-full.json"
    data=json.loads(path.read_text())
    prefixes=("polisyos.fabric.evidence.non_data_acquisition.",
              "polisyos.fabric.evidence.acquisition_assurance.",
              "polisyos.runtime.quality.adaptation_transition.",
              "polisyos.runtime.quality.constrained_response.",
              "polisyos.runtime.quality.operator_comprehension.",
              "polisyos.lex.knowledge.multilingual_assurance.",
              "polisyos.lex.knowledge.locale_census.")
    return {"complete_receipt_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "complete_receipt":str(path),
            **{k:data[k] for k in ("base","denominator","coverage","measured","unmeasured","runtime_invocation_established")},
            "regressions":data["regressions"],"prefix_denominator":prefixes,
            "mechanisms":{k:v for k,v in data["mechanisms"].items() if k.startswith(prefixes)}}


def gyj_report():
    path="architecture/policy_design_case/layer3_gy_graded_outcome_routing_report_v2.json"
    data=json.loads((census.ROOT/path).read_text())
    key=lambda row:(row["run_id"],row["job_id"],row["population_position"])
    members=[key(x) for x in data["population"]["members"]]
    parts={n:[key(x) for x in data[n]] for n in ("graded_outcomes","honest_non_value_outcomes","unmeasurable_outcomes")}
    joined=[k for values in parts.values() for k in values]
    assert len(joined)==len(set(joined)) and set(members)==set(joined)
    assert data["population"]["member_count"]==len(members)
    rate=len(parts["graded_outcomes"])/len(members) if members else None
    assert rate==data["summary"]["useful_design_rate"]
    return {"base":census.BASE,"path":path,"complete_population":members,
            "independently_reconstructed_partitions":parts,"identity_equal":True,
            "numerator":len(parts["graded_outcomes"]),"denominator":len(members),"rate":rate,
            "period":data["population"]["period"],"current_execution_claimed":False,
            "reported_non_value_outcomes":data["honest_non_value_outcomes"]}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=["vocabularies","lex-schema","ukraine","authority","invocation","gyj-report"])
    args=parser.parse_args()
    print(json.dumps({"vocabularies":vocabularies,"lex-schema":lex_schema,
                      "ukraine":ukraine,"authority":authority,"invocation":invocation,
                      "gyj-report":gyj_report}[args.mode](),indent=2,default=str))
