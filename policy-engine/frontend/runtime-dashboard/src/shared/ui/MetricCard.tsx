import type { ReactNode } from "react";

type MetricCardProps = {
  label: string;
  value: ReactNode;
  meta?: ReactNode;
  badge?: ReactNode;
};

export function MetricCard({ label, value, meta, badge }: MetricCardProps) {
  return (
    <article className="bg-surface/75 rounded-2xl border border-line p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs uppercase tracking-wide text-muted">
          {label}
        </span>
        {badge}
      </div>
      <strong className="mt-2 block text-xl font-semibold text-text">
        {value}
      </strong>
      {meta ? <div className="mt-2 text-sm text-muted">{meta}</div> : null}
    </article>
  );
}
