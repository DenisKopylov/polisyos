import type { GlyphIntent, GlyphStrokeStyle } from "@/shared/brand/Glyph";
import type { GlyphName } from "@/shared/brand/glyph-vocabulary";
import type { AuthoredTextAuthor } from "@/shared/ui/authored-text";

export type DecisionPacketSectionType =
  | "problem"
  | "intervention"
  | "evidence"
  | "policy"
  | "governance"
  | "reproducibility";

export type ReadingViewMarginNote = {
  id: string;
  anchorId: string;
  label?: string;
  body: string;
};

export type ReadingViewFootnote = {
  id: string;
  body: string;
  label?: string;
};

export type ReadingViewDefinition = {
  term: string;
  definition: string;
};

export type ReadingViewParagraph = {
  id: string;
  content: string;
  author: AuthoredTextAuthor;
  authorAgentVersion?: string;
  sourceRef?: string;
  timestamp?: string;
  confidence?: number;
  reviewedByHuman?: boolean;
};

export type ReadingViewProvenanceItem = {
  id: string;
  glyph: GlyphName;
  label: string;
  intent?: GlyphIntent;
  strokeStyle?: GlyphStrokeStyle;
  detail?: string;
};

export type ReadingViewSection = {
  id: string;
  title: string;
  sectionType: DecisionPacketSectionType;
  eyebrow?: string;
  lede?: string;
  paragraphs: ReadingViewParagraph[];
  highlights?: string[];
  highlightsTitle?: string;
  pullQuote?: string;
  definitions?: ReadingViewDefinition[];
  marginNotes?: ReadingViewMarginNote[];
  footnotes?: ReadingViewFootnote[];
  provenanceItems?: ReadingViewProvenanceItem[];
};

export type ReadingViewDocument = {
  title: string;
  subtitle?: string;
  deck?: string;
  summary?: string;
  sections: ReadingViewSection[];
};

export const READING_VIEW_MAX_WIDTH = "68ch";
export const READING_VIEW_MARGIN_BREAKPOINT = 1400;
export const READING_VIEW_MARGIN_WIDTH = "18ch";

export const READING_VIEW_SECTION_LABELS: Record<
  DecisionPacketSectionType,
  string
> = {
  problem: "Problem frame",
  intervention: "Intervention",
  evidence: "Evidence",
  policy: "Policy",
  governance: "Governance",
  reproducibility: "Replay",
};

export const READING_VIEW_SECTION_GLYPHS: Record<
  DecisionPacketSectionType,
  GlyphName
> = {
  problem: "blocker",
  intervention: "intervention",
  evidence: "evidence",
  policy: "provenance",
  governance: "governance-pass",
  reproducibility: "reproducibility",
};

export function sectionGlyphForType(
  sectionType: DecisionPacketSectionType,
): GlyphName {
  return READING_VIEW_SECTION_GLYPHS[sectionType];
}

export function sectionLabelForType(
  sectionType: DecisionPacketSectionType,
): string {
  return READING_VIEW_SECTION_LABELS[sectionType];
}
