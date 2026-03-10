import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  body: string;
  actions?: ReactNode;
};

export function EmptyState({ title, body, actions }: EmptyStateProps) {
  return (
    <div className="atlas-empty">
      <h3 className="mb-2 text-lg font-semibold">{title}</h3>
      <p className="mx-auto max-w-xl text-sm text-muted">{body}</p>
      {actions ? <div className="mt-4">{actions}</div> : null}
    </div>
  );
}
