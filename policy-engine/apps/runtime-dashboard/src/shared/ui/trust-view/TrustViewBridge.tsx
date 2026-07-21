import {
  createContext,
  useContext,
  type PropsWithChildren,
} from "react";

import type { VerificationMetadata } from "./trust-glyphs";

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
  temporalScope?: VerificationMetadata["temporal_scope"];
  summary?: string | null;
};

export type TrustViewBridgeValue = {
  mode: TrustViewMode;
  density: "comfortable" | "compact" | "condensed";
  inspectorSubject: TrustInspectorSubject | null;
  setMode: (mode: TrustViewMode, options?: { replaceUrl?: boolean }) => void;
  cycleMode: () => void;
  openInspector: (subject: TrustInspectorSubject) => void;
  closeInspector: () => void;
};

const TrustViewBridgeContext = createContext<TrustViewBridgeValue | null>(null);

export function TrustViewBridgeProvider({
  children,
  value,
}: PropsWithChildren<{ value: TrustViewBridgeValue }>) {
  return (
    <TrustViewBridgeContext.Provider value={value}>
      {children}
    </TrustViewBridgeContext.Provider>
  );
}

export function useTrustView() {
  const context = useContext(TrustViewBridgeContext);
  if (!context) {
    throw new Error("useTrustView must be used within TrustViewBridgeProvider");
  }
  return context;
}

export function useMaybeTrustView() {
  return useContext(TrustViewBridgeContext);
}
