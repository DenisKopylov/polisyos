import process from "node:process";

import { createServer } from "vite";

const server = await createServer({
  appType: "custom",
  logLevel: "silent",
  server: { hmr: false, middlewareMode: true },
});

try {
  const captureModule = await server.ssrLoadModule(
    "/src/test/evidence/captureAtlasEvidence.ts",
  );
  const result = captureModule.captureAtlasEvidence(process.argv.slice(2));
  process.stdout.write(`${JSON.stringify(result)}\n`);
} catch (error) {
  process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
  process.exitCode = 1;
} finally {
  await server.close();
}
