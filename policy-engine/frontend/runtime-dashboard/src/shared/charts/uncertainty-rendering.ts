import type { TrustViewMode } from "@/app/providers/useTrustView";

export function shouldRenderUncertaintyMethodLabel({
  focused = false,
  mode,
}: {
  focused?: boolean;
  mode: TrustViewMode;
}) {
  if (mode === "expanded") {
    return true;
  }
  if (mode === "compact") {
    return focused;
  }
  return false;
}

export function uncertaintyMethodTrustLabel(methodology: string) {
  return methodology.trim();
}
