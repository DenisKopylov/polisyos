import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it } from "vitest";

import {
  checkTokenProjection,
  writeTokenProjection,
} from "../src/tokens/project";

const packageRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const temporaryRoots: string[] = [];

async function copyProjectionTree(): Promise<string> {
  const temporaryRoot = await fs.mkdtemp(
    path.join(os.tmpdir(), "atlas-token-projection-"),
  );
  temporaryRoots.push(temporaryRoot);
  await fs.mkdir(path.join(temporaryRoot, "src"), { recursive: true });
  await fs.cp(
    path.join(packageRoot, "tokens"),
    path.join(temporaryRoot, "tokens"),
    {
      recursive: true,
    },
  );
  await fs.cp(
    path.join(packageRoot, "src/generated"),
    path.join(temporaryRoot, "src/generated"),
    { recursive: true },
  );
  return temporaryRoot;
}

afterEach(async () => {
  await Promise.all(
    temporaryRoots
      .splice(0)
      .map(async (root) => fs.rm(root, { force: true, recursive: true })),
  );
});

describe("DTCG token projection drift", () => {
  async function mutatePrimitiveSource(
    root: string,
    mutate: (source: Record<string, unknown>) => void,
  ) {
    const sourcePath = path.join(root, "tokens/source/primitive.tokens.json");
    const source = JSON.parse(await fs.readFile(sourcePath, "utf8")) as Record<
      string,
      unknown
    >;
    mutate(source);
    await fs.writeFile(sourcePath, JSON.stringify(source, null, 2));
  }

  function zIndexBase(source: Record<string, unknown>) {
    return (
      source as {
        primitive: { zIndex: { base: Record<string, unknown> } };
      }
    ).primitive.zIndex.base;
  }

  it("accepts only the structured DTCG 2025.10 token shapes used by Atlas", async () => {
    const sourceDirectories = ["tokens/source", "tokens/modes"];
    const supportedTypes = new Set([
      "color",
      "cubicBezier",
      "dimension",
      "duration",
      "number",
    ]);

    for (const directory of sourceDirectories) {
      const sourceRoot = path.join(packageRoot, directory);
      for (const name of await fs.readdir(sourceRoot)) {
        const source = JSON.parse(
          await fs.readFile(path.join(sourceRoot, name), "utf8"),
        ) as Record<string, unknown>;
        expect(source.$schema).toBe(
          "https://www.designtokens.org/schemas/2025.10/format.json",
        );

        const visit = (value: unknown): void => {
          if (value === null || typeof value !== "object") return;
          if (Array.isArray(value)) {
            value.forEach(visit);
            return;
          }
          const object = value as Record<string, unknown>;
          if (typeof object.$type === "string") {
            expect(supportedTypes).toContain(object.$type);
            if (object.$type === "color") {
              const color = object.$value as Record<string, unknown>;
              expect(color.colorSpace).toBe("srgb");
              expect(Array.isArray(color.components)).toBe(true);
            }
            if (object.$type === "dimension" || object.$type === "duration") {
              const scalar = object.$value as Record<string, unknown>;
              expect(typeof scalar.unit).toBe("string");
              expect(typeof scalar.value).toBe("number");
            }
            if (object.$type === "cubicBezier") {
              expect(Array.isArray(object.$value)).toBe(true);
              expect(object.$value).toHaveLength(4);
              expect(
                (object.$value as unknown[]).every(
                  (component) => typeof component === "number",
                ),
              ).toBe(true);
            }
            return;
          }
          Object.values(object).forEach(visit);
        };
        visit(source);
      }
    }
  });

  it("keeps only parity-proven primitive leaves in the future authority source", async () => {
    const source = JSON.parse(
      await fs.readFile(
        path.join(packageRoot, "tokens/source/primitive.tokens.json"),
        "utf8",
      ),
    ) as { primitive: Record<string, unknown> };

    expect(Object.keys(source.primitive).sort()).toEqual(["motion", "zIndex"]);
  });

  it("rejects a projection cssValue that disagrees with its canonical DTCG value", async () => {
    const root = await copyProjectionTree();
    const sourcePath = path.join(root, "tokens/modes/motion.tokens.json");
    const source = JSON.parse(await fs.readFile(sourcePath, "utf8")) as {
      motionMode: {
        default: {
          tokens: Record<
            string,
            { $extensions: Record<string, { cssValue: string }> }
          >;
        };
      };
    };
    source.motionMode.default.tokens["--motion-duration-fast"].$extensions[
      "org.polisyos.atlas"
    ].cssValue = "161ms";
    await fs.writeFile(sourcePath, JSON.stringify(source, null, 2));

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "cssValue must equal the canonical DTCG value",
    );
  });

  it("runs the official schema gate before either projection command", async () => {
    const packageJson = JSON.parse(
      await fs.readFile(path.join(packageRoot, "package.json"), "utf8"),
    ) as { scripts: Record<string, string> };

    expect(packageJson.scripts["tokens:check"]).toMatch(
      /^pnpm run tokens:schema && /,
    );
    expect(packageJson.scripts["tokens:generate"]).toMatch(
      /^pnpm run tokens:schema && /,
    );
  });

  it("rejects official-schema-invalid extra composite fields in the direct writer", async () => {
    const root = await copyProjectionTree();
    const sourcePath = path.join(root, "tokens/modes/light.tokens.json");
    const source = JSON.parse(await fs.readFile(sourcePath, "utf8")) as {
      modeLight: {
        tokens: Record<string, { $value: Record<string, unknown> }>;
      };
    };
    source.modeLight.tokens["--canvas"].$value.bogus = 1;
    await fs.writeFile(sourcePath, JSON.stringify(source, null, 2));

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "unsupported color value fields",
    );
  });

  it("rejects official-schema-invalid metadata in the direct writer", async () => {
    const invalidMetadata: Array<{
      expected: string;
      mutate: (source: Record<string, unknown>) => void;
    }> = [
      {
        expected: "$description must be a string",
        mutate: (source) => {
          source.$description = 42;
        },
      },
      {
        expected: "$deprecated must be a boolean or string",
        mutate: (source) => {
          zIndexBase(source).$deprecated = { reason: "replaced" };
        },
      },
    ];

    for (const { expected, mutate } of invalidMetadata) {
      const root = await copyProjectionTree();
      await mutatePrimitiveSource(root, mutate);
      await expect(writeTokenProjection(root)).rejects.toThrow(expected);
    }
  });

  it("rejects an official-schema-invalid token or group name in the direct writer", async () => {
    const root = await copyProjectionTree();
    await mutatePrimitiveSource(root, (source) => {
      (source.primitive as Record<string, unknown>)["hidden.token"] = {
        $type: "number",
        $value: 1,
      };
    });

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "DTCG token and group names must not start with $ or contain braces or periods",
    );
  });

  it("rejects an official-schema-invalid cubic-bezier x coordinate in the direct writer", async () => {
    const root = await copyProjectionTree();
    const sourcePath = path.join(root, "tokens/modes/motion.tokens.json");
    const source = JSON.parse(await fs.readFile(sourcePath, "utf8")) as {
      motionMode: {
        default: {
          tokens: Record<
            string,
            {
              $extensions: Record<string, { cssValue: string }>;
              $type: string;
              $value: number[];
            }
          >;
        };
      };
    };
    const easing = Object.values(source.motionMode.default.tokens).find(
      (token) => token.$type === "cubicBezier",
    );
    expect(easing).toBeDefined();
    if (!easing) throw new TypeError("expected a cubicBezier fixture");
    easing.$value[0] = 2;
    easing.$extensions["org.polisyos.atlas"].cssValue =
      `cubic-bezier(${easing.$value.join(", ")})`;
    await fs.writeFile(sourcePath, JSON.stringify(source, null, 2));

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "cubicBezier x coordinates must be between zero and one",
    );
  });

  it("preserves a valid DTCG color alpha in the CSS projection", async () => {
    const root = await copyProjectionTree();
    const sourcePath = path.join(root, "tokens/modes/light.tokens.json");
    const source = JSON.parse(await fs.readFile(sourcePath, "utf8")) as {
      modeLight: {
        tokens: Record<
          string,
          {
            $extensions: Record<string, { cssValue: string }>;
            $value: Record<string, unknown>;
          }
        >;
      };
    };
    const canvas = source.modeLight.tokens["--canvas"];
    canvas.$value.alpha = 0.5;
    canvas.$extensions["org.polisyos.atlas"].cssValue =
      "rgb(239 233 220 / 0.5)";
    await fs.writeFile(sourcePath, JSON.stringify(source, null, 2));

    await writeTokenProjection(root);

    expect(
      await fs.readFile(path.join(root, "src/generated/tokens.css"), "utf8"),
    ).toContain("--canvas: rgb(239 233 220 / 0.5);");
  });

  it("faithfully projects a valid DTCG none color component", async () => {
    const root = await copyProjectionTree();
    const sourcePath = path.join(root, "tokens/modes/light.tokens.json");
    const source = JSON.parse(await fs.readFile(sourcePath, "utf8")) as {
      modeLight: {
        tokens: Record<
          string,
          {
            $extensions: Record<string, { cssValue: string }>;
            $value: { components: Array<number | "none"> };
          }
        >;
      };
    };
    const canvas = source.modeLight.tokens["--canvas"];
    canvas.$value.components[0] = "none";
    canvas.$extensions["org.polisyos.atlas"].cssValue =
      "rgb(none 233 220)";
    await fs.writeFile(sourcePath, JSON.stringify(source, null, 2));

    await writeTokenProjection(root);

    const css = await fs.readFile(
      path.join(root, "src/generated/tokens.css"),
      "utf8",
    );
    expect(css).toContain("--canvas: rgb(none 233 220);");
    expect(css).not.toContain("NaN");
  });

  it("rejects a corrupted generated value while source markers remain intact", async () => {
    const root = await copyProjectionTree();
    const cssPath = path.join(root, "src/generated/tokens.css");
    const original = await fs.readFile(cssPath, "utf8");
    expect(original).toContain("@generated");
    expect(original).toContain("source-digest:");
    await fs.writeFile(
      cssPath,
      original.replace("--z-command: 600", "--z-command: 601"),
    );

    const result = await checkTokenProjection(root);

    expect(result.ok).toBe(false);
    expect(result.diagnostics).toContain(
      "src/generated/tokens.css differs from deterministic projection",
    );
  });

  it("rejects hand-edited generated output", async () => {
    const root = await copyProjectionTree();
    const tokensPath = path.join(root, "src/generated/tokens.ts");
    await fs.appendFile(tokensPath, "\n// hand edited while header remains\n");

    const result = await checkTokenProjection(root);

    expect(result.ok).toBe(false);
    expect(result.diagnostics).toContain(
      "src/generated/tokens.ts differs from deterministic projection",
    );
  });

  it("rejects source drift against unchanged generated outputs", async () => {
    const root = await copyProjectionTree();
    const sourcePath = path.join(root, "tokens/source/primitive.tokens.json");
    const source = await fs.readFile(sourcePath, "utf8");
    await fs.writeFile(
      sourcePath,
      source.replace('"$value": 600', '"$value": 601'),
    );

    const result = await checkTokenProjection(root);

    expect(result.ok).toBe(false);
    expect(result.diagnostics).toContain(
      "src/generated/manifest.json differs from deterministic projection",
    );
    expect(result.diagnostics).toContain(
      "src/generated/tokens.css differs from deterministic projection",
    );
  });

  it("rejects a hand-edited projection manifest", async () => {
    const root = await copyProjectionTree();
    const manifestPath = path.join(root, "src/generated/manifest.json");
    const manifest = await fs.readFile(manifestPath, "utf8");
    await fs.writeFile(
      manifestPath,
      manifest.replace('"schemaVersion": 1', '"schemaVersion": 99'),
    );

    const result = await checkTokenProjection(root);

    expect(result.ok).toBe(false);
    expect(result.diagnostics).toContain(
      "src/generated/manifest.json differs from deterministic projection",
    );
  });

  it("rejects an unregistered sibling generated alias", async () => {
    const root = await copyProjectionTree();
    await fs.writeFile(
      path.join(root, "src/generated/tokens-sibling.ts"),
      "export const unregisteredAlias = 'var(--color-transport-live)';\n",
    );

    const result = await checkTokenProjection(root);

    expect(result.ok).toBe(false);
    expect(result.diagnostics).toContain(
      "unexpected generated output: src/generated/tokens-sibling.ts",
    );
  });

  it("rejects an unknown DTCG type before regeneration can bless it", async () => {
    const root = await copyProjectionTree();
    await mutatePrimitiveSource(root, (source) => {
      zIndexBase(source).$type = "definitely-not-a-dtcg-type";
    });

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "unsupported DTCG $type",
    );
  });

  it("rejects missing DTCG type and value members", async () => {
    const missingTypeRoot = await copyProjectionTree();
    await mutatePrimitiveSource(missingTypeRoot, (source) => {
      delete zIndexBase(source).$type;
    });
    await expect(writeTokenProjection(missingTypeRoot)).rejects.toThrow(
      "must declare both $type and $value",
    );

    const missingValueRoot = await copyProjectionTree();
    await mutatePrimitiveSource(missingValueRoot, (source) => {
      delete zIndexBase(source).$value;
    });
    await expect(writeTokenProjection(missingValueRoot)).rejects.toThrow(
      "must declare both $type and $value",
    );
  });

  it("rejects a malformed value for its declared DTCG type", async () => {
    const root = await copyProjectionTree();
    await mutatePrimitiveSource(root, (source) => {
      zIndexBase(source).$value = { unit: "px", value: 0 };
    });

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "number token must contain a finite number",
    );
  });

  it("rejects a nested sibling hidden beside a DTCG token", async () => {
    const root = await copyProjectionTree();
    await mutatePrimitiveSource(root, (source) => {
      zIndexBase(source).shadowSibling = {
        $type: "number",
        $value: 999,
      };
    });

    await expect(writeTokenProjection(root)).rejects.toThrow(
      "token must not contain nested siblings",
    );
  });
});
