import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

describe("shared/ui accessibility coverage", () => {
  it("keeps an a11y test next to every component unless explicitly allowlisted", () => {
    const directory = path.dirname(fileURLToPath(import.meta.url));
    const allowlist = new Set<string>([
      "counterfactual/AssumptionPill.tsx",
      "counterfactual/CounterfactualBadge.tsx",
      "counterfactual/CounterfactualDelta.tsx",
      "counterfactual/CounterfactualMetricChart.tsx",
      "counterfactual/CounterfactualModeSwitch.tsx",
      "counterfactual/DualInput.tsx",
      "counterfactual/DualSelector.tsx",
      "counterfactual/DualSlider.tsx",
      "counterfactual/ScenarioManifestPanel.tsx",
      "counterfactual/ScenarioPicker.tsx",
      "quantity/CounterfactualQuantity.tsx",
      "quantity/ProvenanceDeepDiveDialog.tsx",
      "quantity/ProvenanceMiniGraph.tsx",
      "temporal/TemporalCapabilityBanner.tsx",
      "temporal/TemporalCursorMarker.tsx",
      "temporal/TemporalLegend.tsx",
      "temporal/withTemporalCursor.tsx",
      "trust-view/DisputeBadge.tsx",
      "trust-view/HashChip.tsx",
      "trust-view/TemporalScopeChip.tsx",
      "trust-view/TrustInspector.tsx",
      "trust-view/TrustMetadata.tsx",
      "trust-view/TrustViewBadge.tsx",
      "trust-view/TrustViewToggle.tsx",
      "trust-view/VerificationStatus.tsx",
    ]);

    function collectComponentFiles(currentDirectory: string, prefix = "") {
      const entries = fs.readdirSync(currentDirectory, { withFileTypes: true });
      const files: string[] = [];

      for (const entry of entries) {
        const relativePath = prefix ? `${prefix}/${entry.name}` : entry.name;
        const absolutePath = path.join(currentDirectory, entry.name);

        if (entry.isDirectory()) {
          files.push(...collectComponentFiles(absolutePath, relativePath));
          continue;
        }
        if (!entry.isFile() || !entry.name.endsWith(".tsx")) {
          continue;
        }
        if (
          entry.name.endsWith(".a11y.test.tsx") ||
          entry.name.endsWith(".stories.tsx") ||
          entry.name.endsWith(".test.tsx") ||
          entry.name === "index.tsx"
        ) {
          continue;
        }
        files.push(relativePath);
      }

      return files;
    }

    const componentFiles = collectComponentFiles(directory);

    const missing = componentFiles.filter((entry) => {
      if (allowlist.has(entry)) {
        return false;
      }

      const baseName = entry.replace(/\.tsx$/, "");
      return !fs.existsSync(path.join(directory, `${baseName}.a11y.test.tsx`));
    });

    expect(missing).toEqual([]);
  });
});
