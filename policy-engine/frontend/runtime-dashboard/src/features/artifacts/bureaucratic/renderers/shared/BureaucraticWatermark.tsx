import { ShieldAlert } from "lucide-react";

import { cn } from "@/shared/lib/utils";

type BureaucraticWatermarkProps = {
  watermark: string;
  className?: string;
};

export function BureaucraticWatermark({
  watermark,
  className,
}: BureaucraticWatermarkProps) {
  return (
    <div
      className={cn(
        "border-warning/40 bg-warning/10 text-warning flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-semibold print:border-black print:bg-transparent print:text-black",
        className,
      )}
      role="note"
      aria-label={watermark}
    >
      <ShieldAlert className="size-4" aria-hidden="true" />
      <span>{watermark}</span>
    </div>
  );
}
