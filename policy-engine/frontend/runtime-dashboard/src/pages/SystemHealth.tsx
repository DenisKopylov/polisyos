import { useHealth } from "../api/hooks/useHealth";
import StatusBadge from "../components/shared/StatusBadge";
import { Card } from "../components/ui/card";

export default function SystemHealth() {
  const healthQuery = useHealth();

  return (
    <Card>
      <h2 className="mb-3 text-xl font-semibold">System Health</h2>
      {healthQuery.isLoading ? <p className="text-sm text-muted">Checking runtime API...</p> : null}
      {healthQuery.isError ? (
        <p className="text-sm text-danger">{String(healthQuery.error)}</p>
      ) : null}
      {healthQuery.data ? (
        <div className="space-y-2 text-sm">
          <StatusBadge label={healthQuery.data.status} kind={healthQuery.data.status === "ok" ? "ok" : "warn"} />
          {healthQuery.data.service ? <p>service: {healthQuery.data.service}</p> : null}
          {healthQuery.data.ts ? <p>ts: {healthQuery.data.ts}</p> : null}
        </div>
      ) : null}
    </Card>
  );
}
