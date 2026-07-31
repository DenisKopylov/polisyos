import type { VerificationMetadata } from "@polisyos/runtime-api-client";

import type { GlyphStrokeStyle } from "./Glyph";
import type { GlyphName } from "./glyph-vocabulary";

export type ProvenanceItem = {
  id: string;
  glyph: GlyphName;
  label: string;
  strokeStyle?: GlyphStrokeStyle;
  detail?: string;
  trustMetadata?: VerificationMetadata | null;
};
