const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');
const root = '/workspace/e02-E-continuation-20261006/policy-engine/apps/runtime-dashboard';
const dashboardRequire = createRequire(path.join(root, 'package.json'));
const { chromium } = dashboardRequire('playwright');
const profile = '/workspace/e02-E-pr38-r2-receipts/independent-wave-harness/chromium-profile';
if (fs.existsSync(profile)) throw new Error('Refuse reused browser profile');
const result = {
  node: process.version,
  cwd: process.cwd(),
  browserCache: process.env.PLAYWRIGHT_BROWSERS_PATH,
  packagePath: fs.realpathSync(dashboardRequire.resolve('playwright/package.json')),
  playwrightVersion: dashboardRequire('playwright/package.json').version,
  testVersion: dashboardRequire('@playwright/test/package.json').version,
  chromiumExecutablePath: chromium.executablePath(),
  persistentProfile: profile,
  scope: 'Browser launch/render capability only; no doctor/full-CI/browser-suite/numerical PASS inferred'
};
(async () => {
  const context = await chromium.launchPersistentContext(profile, { headless: true });
  try {
    const page = await context.newPage();
    await page.setContent('<p id="capability">4</p>');
    result.browserVersion = context.browser().version();
    result.actualRenderedText = await page.locator('#capability').textContent();
    if (result.actualRenderedText !== '4') throw new Error('Native browser render oracle failed');
    result.outcome = 'PASS-browser-capability';
  } finally {
    await context.close();
  }
  fs.writeFileSync('/workspace/e02-E-pr38-r2-receipts/independent-wave-harness/browser-capability.json', JSON.stringify(result, null, 2) + '\n');
  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
})().catch(error => {
  result.outcome = 'ERROR-browser-unavailable'; result.error = String(error);
  process.stdout.write(JSON.stringify(result, null, 2) + '\n'); process.exitCode = 1;
});
