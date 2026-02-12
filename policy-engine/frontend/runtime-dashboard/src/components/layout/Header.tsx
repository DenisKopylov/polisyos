import { Link } from "react-router-dom";

import { useHealth } from "../../api/hooks/useHealth";
import StatusBadge from "../shared/StatusBadge";

function resolveHealthBadge(status: string | undefined) {
  if (status === "ok") {
    return <StatusBadge label="API OK" kind="ok" />;
  }
  if (status) {
    return <StatusBadge label={status} kind="warn" />;
  }
  return <StatusBadge label="Unknown" kind="unknown" />;
}

export default function Header() {
  const healthQuery = useHealth();

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-panel/85 px-4 py-3 md:px-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Runtime API v1</p>
        <p className="text-sm text-muted">Read-only frontend for run and artifact introspection</p>
      </div>

      <div className="flex items-center gap-3">
        {healthQuery.isLoading ? <StatusBadge label="Checking" kind="unknown" /> : null}
        {healthQuery.isError ? <StatusBadge label="Unavailable" kind="fail" /> : null}
        {!healthQuery.isLoading && !healthQuery.isError
          ? resolveHealthBadge(healthQuery.data?.status)
          : null}
        <Link to="/runs" className="rounded-lg border border-line bg-panel px-3 py-2 text-sm font-medium">
          Open Run Explorer
        </Link>
      </div>
    </header>
  );
}
