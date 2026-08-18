import process from "node:process";
import { fileURLToPath } from "node:url";

import { createServer } from "vite";

if (process.argv.length !== 2) {
  process.stderr.write(
    "measure_atlas_health accepts no caller-supplied report, root, script, exit, basis, or arguments\n",
  );
  process.exitCode = 1;
} else {
  const dashboardRoot = fileURLToPath(new URL("..", import.meta.url));
  process.chdir(dashboardRoot);
  const server = await createServer({
    appType: "custom",
    logLevel: "silent",
    root: dashboardRoot,
    server: { hmr: false, middlewareMode: true },
  });

  try {
    const metricModule = await server.ssrLoadModule(
      "/src/test/evidence/atlasHealthMetrics.ts",
    );
    const report = metricModule.measureAtlasHealthMetrics();
    process.stdout.write(`${JSON.stringify(report)}\n`);
  } catch (error) {
    process.stderr.write(
      `${error instanceof Error ? error.stack : String(error)}\n`,
    );
    process.exitCode = 1;
  } finally {
    await server.close();
  }
}
