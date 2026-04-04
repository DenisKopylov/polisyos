import type { ReactNode } from "react";

type MetricCardProps = {
  label: string;
  value: ReactNode;
  meta?: ReactNode;
  badge?: ReactNode;
};

export function MetricCard({ label, value, meta, badge }: MetricCardProps) {
  return (
    <article className="bg-surface/75 border-line rounded-2xl border p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted text-xs tracking-wide uppercase">
          {label}
        </span>
        {badge}
      </div>
      <strong className="text-text mt-2 block text-xl font-semibold">
        {value}
      </strong>
      {meta ? <div className="text-muted mt-2 text-sm">{meta}</div> : null}
    </article>
  );
}
