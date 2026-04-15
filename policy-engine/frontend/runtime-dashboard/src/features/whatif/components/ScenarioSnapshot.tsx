import { useCallback, useEffect, useRef, useState } from "react";

import { cn, formatDate } from "@/lib/utils";
import { Button, Card } from "@/shared/ui/primitives";

import type { Scenario } from "../types";
import { useWhatIfStore } from "../state/useWhatIfStore";

type ScenarioSnapshotProps = {
  onCompare?: (scenarioId: string) => void;
  className?: string;
};

export function ScenarioSnapshot({
  onCompare,
  className,
}: ScenarioSnapshotProps) {
  const { scenarios, saveScenario, deleteScenario, loadScenario } =
    useWhatIfStore();
  const [showSave, setShowSave] = useState(false);
  const [name, setName] = useState("");
  const saveNameInputRef = useRef<HTMLInputElement | null>(null);

  const handleSave = useCallback(() => {
    const label = name.trim() || `Scenario ${scenarios.length + 1}`;
    saveScenario(label);
    setName("");
    setShowSave(false);
  }, [name, scenarios.length, saveScenario]);

  useEffect(() => {
    if (showSave) {
      saveNameInputRef.current?.focus();
    }
  }, [showSave]);

  return (
    <Card className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">
          Scenarios ({scenarios.length})
        </h4>
        <Button
          type="button"
          variant="ghost"
          onClick={() => setShowSave(!showSave)}
        >
          {showSave ? "Cancel" : "+ Save current"}
        </Button>
      </div>

      {/* Save form */}
      {showSave && (
        <div className="flex gap-2">
          <input
            ref={saveNameInputRef}
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Scenario name"
            className="bg-surface border-line flex-1 rounded-lg border px-2 py-1 text-sm"
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
            }}
          />
          <Button type="button" variant="primary" onClick={handleSave}>
            Save
          </Button>
        </div>
      )}

      {/* Scenario list */}
      {scenarios.length === 0 ? (
        <p className="text-muted text-sm">
          No scenarios saved yet. Adjust parameters and save.
        </p>
      ) : (
        <div className="space-y-2">
          {scenarios.map((scenario) => (
            <ScenarioRow
              key={scenario.id}
              scenario={scenario}
              onLoad={() => loadScenario(scenario.id)}
              onDelete={() => deleteScenario(scenario.id)}
              onCompare={
                onCompare
                  ? () => onCompare(scenario.id)
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </Card>
  );
}

function ScenarioRow({
  scenario,
  onLoad,
  onDelete,
  onCompare,
}: {
  scenario: Scenario;
  onLoad: () => void;
  onDelete: () => void;
  onCompare?: () => void;
}) {
  const paramCount = Object.keys(scenario.parameters).length;

  return (
    <div className="border-line flex items-center gap-3 rounded-xl border p-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{scenario.name}</p>
        <div className="text-muted mt-0.5 flex flex-wrap gap-2 text-xs">
          <span>{paramCount} params</span>
          {scenario.metrics && (
            <span>{scenario.metrics.length} metrics</span>
          )}
          <span>
            {formatDate(scenario.createdAt, undefined, {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </div>
      <div className="flex shrink-0 gap-1">
        <button
          type="button"
          onClick={onLoad}
          className="text-muted hover:text-inherit rounded-lg px-2 py-1 text-xs font-medium"
          title="Load parameters"
        >
          Load
        </button>
        {onCompare && (
          <button
            type="button"
            onClick={onCompare}
            className="rounded-lg px-2 py-1 text-xs font-medium text-[var(--chart-primary)]"
            title="Compare with base run"
          >
            Compare
          </button>
        )}
        <button
          type="button"
          onClick={onDelete}
          className="text-muted hover:text-[var(--chart-alert)] rounded-lg px-2 py-1 text-xs"
          title="Delete scenario"
        >
          {"\u2715"}
        </button>
      </div>
    </div>
  );
}
