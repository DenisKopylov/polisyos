import type { TrustViewMode } from "@/shared/ui/trust-view";

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
