import type { GlyphIntent, GlyphStrokeStyle } from "./Glyph";
import type { GlyphName } from "./glyph-vocabulary";
import { resolveGlyphForTerm } from "./glyph-vocabulary";

/**
 * Canonical `EvidenceFabricItem` subset the adapter understands. Only the
 * fields consumed by `ProvenanceStrip` are listed; the adapter is tolerant
 * of missing fields.
 */
export type EvidenceFabricItem = {
  fresh_at?: string | null;
  governance_pass?: boolean | null;
  intervention_type?: string | null;
  evidence_strength?: string | null;
  label?: string;
  [key: string]: unknown;
};

export type ProvenanceItem = {
  id: string;
  glyph: GlyphName;
  label: string;
  intent?: GlyphIntent;
  strokeStyle?: GlyphStrokeStyle;
  detail?: string;
};

const STALE_AFTER_MS = 30 * 60_000; // 30 minutes

function labelForFreshness(freshAt: string): {
  label: string;
  intent: GlyphIntent;
} {
  const timestamp = Date.parse(freshAt);
  if (Number.isNaN(timestamp)) {
    return { label: "Freshness unknown", intent: "pending" };
  }
  const age = Date.now() - timestamp;
  if (age < 0) {
    return { label: "Fresh", intent: "verified" };
  }
  if (age > STALE_AFTER_MS) {
    return { label: "Stale", intent: "blocked" };
  }
  return { label: "Fresh", intent: "verified" };
}

export type ProvenanceAdapterOptions = {
  maxItems?: number;
  now?: number;
};

export function evidenceFabricItemToProvenance(
  item: EvidenceFabricItem,
  options: ProvenanceAdapterOptions = {},
): ProvenanceItem[] {
  const items: ProvenanceItem[] = [];
  const push = (entry: ProvenanceItem) => {
    items.push(entry);
  };

  if (typeof item.fresh_at === "string" && item.fresh_at.length > 0) {
    const { label, intent } = labelForFreshness(item.fresh_at);
    push({
      id: "freshness",
      glyph: "freshness",
      label,
      intent,
      detail: item.fresh_at,
    });
  }

  if (typeof item.governance_pass === "boolean") {
    push(
      item.governance_pass
        ? {
            id: "governance",
            glyph: "governance-pass",
            label: "Governance pass",
            intent: "verified",
          }
        : {
            id: "governance",
            glyph: "blocker",
            label: "Governance blocked",
            intent: "blocked",
          },
    );
  }

  if (
    typeof item.intervention_type === "string" &&
    item.intervention_type.length > 0
  ) {
    const mapped = resolveGlyphForTerm(item.intervention_type) ?? "intervention";
    push({
      id: "intervention",
      glyph: mapped,
      label: item.intervention_type,
      intent: "default",
    });
  }

  if (typeof item.evidence_strength === "string") {
    const strong = item.evidence_strength === "strong";
    push({
      id: "evidence",
      glyph: "evidence",
      label: strong ? "Strong evidence" : "Weak evidence",
      intent: strong ? "verified" : "pending",
      strokeStyle: strong ? "solid" : "dashed",
    });
  }

  const max = options.maxItems ?? 8;
  return items.slice(0, max);
}

export function provenanceFromFabricItems(
  fabric: EvidenceFabricItem[],
  options?: ProvenanceAdapterOptions,
): ProvenanceItem[] {
  const reduced = new Map<string, ProvenanceItem>();
  for (const item of fabric) {
    for (const provenanceItem of evidenceFabricItemToProvenance(
      item,
      options,
    )) {
      if (!reduced.has(provenanceItem.id)) {
        reduced.set(provenanceItem.id, provenanceItem);
      }
    }
  }
  return Array.from(reduced.values());
}
