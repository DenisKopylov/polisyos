"""Reconcile all B criterion owners with exact six-family Git receipts."""

from collections import Counter, defaultdict
import hashlib
import json
from b_family_inputs import (
    ORG_ROOT, arguments, blob, declared_source_points, disposition_rows, git,
    ordered_receipts, owner_tables, receipt_source_commit_ids, write_output,
)


def main():
    args, final, heads = arguments("Complete B owner/receipt reconciliation; no closure inference")
    all_bundles, all_findings = owner_tables(final)
    bundles = [r for r in all_bundles if r["unit"] == "B"]
    findings = [r for r in all_findings if r["unit"] == "B"]
    errors, warnings = [], []
    denominators = {
        "all_bundles": len(all_bundles), "all_findings": len(all_findings),
        "B_bundles": len(bundles), "B_findings": len(findings),
    }
    if denominators != {"all_bundles": 127, "all_findings": 282,
                        "B_bundles": 25, "B_findings": 60}:
        errors.append({"kind": "canonical_denominator_changed", "observed": denominators})
    for key, rows in [("bundle_id", all_bundles), ("finding_id", all_findings)]:
        duplicates = sorted(k for k, n in Counter(r[key] for r in rows).items() if n != 1)
        if duplicates:
            errors.append({"kind": "duplicate_canonical_key", "key": key, "values": duplicates})
    canonical_bundles = {r["bundle_id"] for r in bundles}
    canonical_findings = {r["finding_id"]: r for r in findings}
    claims, family_metadata = defaultdict(list), {}
    for family in sorted(heads):
        effective, histories, sources, advertised = {}, defaultdict(list), [], set()
        for priority, (path, doc) in enumerate(ordered_receipts(args, heads, family)):
            ids = []
            for finding_id, index, row in disposition_rows(doc):
                if not finding_id:
                    errors.append({"kind": "missing_finding_key", "family": family,
                                   "receipt": path, "index": index})
                    continue
                ids.append(finding_id)
                location = {"source_receipt": f"{path}@{heads[family]}",
                            "receipt_blob": blob(heads[family], path),
                            "disposition_index": index, "priority": priority,
                            "disposition_sha256": hashlib.sha256(
                                json.dumps(row, sort_keys=True, ensure_ascii=False,
                                           separators=(",", ":")).encode()).hexdigest()}
                histories[finding_id].append(location)
                effective[finding_id] = (path, index, priority, row)
            repeated = sorted(k for k, n in Counter(ids).items() if n != 1)
            if repeated:
                errors.append({"kind": "duplicate_finding_within_receipt", "family": family,
                               "receipt": path, "ids": repeated})
            declared = set(doc.get("bundle_ids", []))
            advertised.update(declared)
            sources.append({"priority": priority, "kind": "main" if priority == 0 else "overlay",
                            "source_receipt": f"{path}@{heads[family]}",
                            "receipt_blob": blob(heads[family], path),
                            "finding_count": len(ids), "advertised_bundles": sorted(declared),
                            "explicit_source_identity": declared_source_points(doc)})
        ids = sorted(effective)
        for finding_id, (path, index, priority, row) in effective.items():
            claims[finding_id].append((family, path, index, priority, histories[finding_id], row))
        expected_bundles = {canonical_findings[i]["source_closure_owner"]
                            for i in ids if i in canonical_findings}
        missing = sorted(expected_bundles - advertised)
        extra = sorted(advertised - expected_bundles)
        if missing or extra:
            warnings.append({"kind": "advertised_bundle_scope_mismatch", "family": family,
                             "missing_advertised_bundles": missing,
                             "extra_advertised_bundles": extra,
                             "note": "Criterion-owner join is explicit; never treat closure_ids as scope."})
        family_metadata[family] = {
            "head": heads[family], "ordered_receipts": sources,
            "finding_count": len(ids), "canonical_owned_bundles": sorted(expected_bundles),
            "advertised_bundles": sorted(advertised),
            "explicit_final_source_point": args.source_points.get(family),
            "source_point_declared_in_ordered_receipts":
                args.source_points.get(family) in set().union(*[
                    receipt_source_commit_ids(doc)
                    for _, doc in ordered_receipts(args, heads, family)])
                if family in args.source_points else None,
            "head_is_ancestor_of_final":
                __import__("subprocess").run(["git", "-C", str(args.repo), "merge-base",
                                              "--is-ancestor", heads[family], final]).returncode == 0,
        }
    missing_ids = sorted(set(canonical_findings) - set(claims))
    foreign_ids = sorted(set(claims) - set(canonical_findings))
    overlaps = {i: [r[0] for r in rows] for i, rows in sorted(claims.items()) if len(rows) != 1}
    if missing_ids or foreign_ids or overlaps:
        errors.append({"kind": "finding_partition_failure", "missing_ids": missing_ids,
                       "foreign_ids": foreign_ids, "overlaps": overlaps})
    joined = []
    for finding_id, canonical in sorted(canonical_findings.items()):
        family_claims = claims.get(finding_id, [])
        owner = canonical["source_closure_owner"]
        if owner not in canonical_bundles:
            errors.append({"kind": "finding_owner_not_B_bundle", "id": finding_id, "owner": owner})
        for family, path, index, priority, history, disposition in family_claims:
            joined.append({"finding_id": finding_id, "canonical_bundle": owner,
                           "unit": "B", "family": family, "head": heads[family],
                           "source_receipt": f"{path}@{heads[family]}",
                           "disposition_index": index, "priority": priority,
                           "ordered_disposition_history": history,
                           "effective_disposition": disposition,
                           "canonical_source_status": canonical["source_status"],
                           "canonical_owner_row": canonical})
    covered_bundles = {row["canonical_bundle"] for row in joined}
    bundle_families = defaultdict(set)
    for row in joined:
        bundle_families[row["canonical_bundle"]].add(row["family"])
    split_bundles = {bundle: sorted(families) for bundle, families in sorted(bundle_families.items())
                     if len(families) != 1}
    if split_bundles:
        errors.append({"kind": "canonical_bundle_multiple_family_owners", "bundles": split_bundles})
    if covered_bundles != canonical_bundles:
        errors.append({"kind": "canonical_bundle_partition_failure",
                       "missing": sorted(canonical_bundles - covered_bundles),
                       "extra": sorted(covered_bundles - canonical_bundles)})
    report = {
        "schema": "policyos.e02.B_owner_reconciliation.v1", "final_head": final,
        "final_tree": git("rev-parse", final + "^{tree}").strip(),
        "source_tables": [f"{ORG_ROOT}/{name}.tsv@{final}"
                          for name in ["bundle-owners", "finding-owners"]],
        "source_table_blobs": {name: blob(final, f"{ORG_ROOT}/{name}.tsv")
                               for name in ["bundle-owners", "finding-owners"]},
        "denominators": denominators, "families": family_metadata,
        "findings": joined, "canonical_owned_bundles": sorted(covered_bundles),
        "errors": errors, "warnings": warnings,
        "bookkeeping_outcome": "FAIL" if errors else "PASS_with_declaration_warnings" if warnings else "PASS",
        "formal_closure_or_runtime_acceptance": "not_established_by_this_metadata_join",
        "overlay_policy": "Base entry plus explicit CLI overlays in order; only the same family's per-ID entries supersede. No directory walk or arbitrary last JSON.",
        "lineage_limit": "Ancestor flags disclose merge state; they are not a substitute for code/input/content review.",
    }
    write_output(args.output, report)
    print(report["bookkeeping_outcome"], denominators,
          "errors", len(errors), "warnings", len(warnings), str(args.output))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
