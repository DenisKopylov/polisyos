import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve("apps/runtime-dashboard/src/shared/i18n/locales");
const files = (await readdir(root)).filter((file) => file.endsWith(".json")).sort();
const catalogs = new Map(
  await Promise.all(
    files.map(async (file) => [
      file,
      JSON.parse(await readFile(path.join(root, file), "utf8")),
    ]),
  ),
);

function comparePaths(left, right) {
  return left < right ? -1 : left > right ? 1 : 0;
}

function collectLeaves(value, prefix = "") {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return prefix ? [[prefix, value]] : [];
  }
  return Object.entries(value).flatMap(([key, nested]) =>
    collectLeaves(nested, prefix ? `${prefix}.${key}` : key),
  );
}

function digest(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

const perFile = files.map((file) => {
  const leaves = collectLeaves(catalogs.get(file));
  return { file, file_type: ".json", leaf_count: leaves.length };
});
const ruLeaves = collectLeaves(catalogs.get("ru.json")).sort(([left], [right]) =>
  comparePaths(left, right),
);
const ruKeys = ruLeaves.map(([key]) => key);

process.stdout.write(
  `${JSON.stringify(
    {
      scope: "all locale JSON files in apps/runtime-dashboard/src/shared/i18n/locales",
      file_type_denominator: ".json",
      file_count: files.length,
      files: perFile,
      ru_key_count: ruKeys.length,
      ru_key_set_sha256: digest(ruKeys),
      ru_leaf_value_sha256: digest(ruLeaves),
    },
    null,
    2,
  )}\n`,
);
