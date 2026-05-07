import { createContext, useContext } from "react";

import type { TemporalRef } from "@/shared/ui/quantity";
import type { VerificationMetadata } from "@/shared/ui/trust-view/trust-glyphs";

export type TrustViewMode = "off" | "compact" | "expanded";

export type TrustInspectorSubjectKind =
  | "quantity"
  | "authored_text"
  | "artifact"
  | "lineage"
  | "chart";

export type TrustInspectorSubject = {
  id: string;
  kind: TrustInspectorSubjectKind;
  label?: string | null;
  hash?: string | null;
  trustMetadata?: VerificationMetadata | null;
  temporalScope?: TemporalRef | null;
  summary?: string | null;
};

export type TrustViewContextValue = {
  mode: TrustViewMode;
  density: "comfortable" | "compact" | "condensed";
  inspectorSubject: TrustInspectorSubject | null;
  setMode: (mode: TrustViewMode, options?: { replaceUrl?: boolean }) => void;
  cycleMode: () => void;
  openInspector: (subject: TrustInspectorSubject) => void;
  closeInspector: () => void;
};

export const TrustViewContext = createContext<TrustViewContextValue | null>(
  null,
);

export function useTrustView() {
  const context = useContext(TrustViewContext);
  if (!context) {
    throw new Error("useTrustView must be used within TrustViewProvider");
  }
  return context;
}

export function useMaybeTrustView() {
  return useContext(TrustViewContext);
}
