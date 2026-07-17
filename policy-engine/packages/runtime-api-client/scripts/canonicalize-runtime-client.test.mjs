import assert from "node:assert/strict";
import test from "node:test";

import { canonicalizeRuntimeClientSource } from "./canonicalize-runtime-client.mjs";

const GENERATED_SOURCE = `// GENERATED FILE. DO NOT EDIT.
// Source: schemas/runtime_api_v1.openapi.json

export type JsonValue = string | number;

export type AvailableGovernedProjectionPacket = {
  availability: string;
  packet_schema_version?: string;
};

export type ChannelRegistryEntry = {
  capability_state?: string;
};

export type ArtifactRefInput = {
  artifact_id: string;
};

export interface RuntimeApiClientOptions {
  baseUrl: string;
}

export class RuntimeApiClient {}
`;

test("canonicalization aliases every generated OpenAPI component to types.ts", () => {
  const canonicalized = canonicalizeRuntimeClientSource(GENERATED_SOURCE, [
    "AvailableGovernedProjectionPacket",
    "ChannelRegistryEntry",
    "ArtifactRef-Input",
  ]);

  assert.ok(
    canonicalized.includes(
      [
        "import",
        'type { components as RuntimeApiComponents } from "./types.js";',
      ].join(" "),
    ),
  );
  assert.match(
    canonicalized,
    /export type AvailableGovernedProjectionPacket = RuntimeApiComponents\["schemas"\]\["AvailableGovernedProjectionPacket"\];/,
  );
  assert.match(
    canonicalized,
    /export type ChannelRegistryEntry = RuntimeApiComponents\["schemas"\]\["ChannelRegistryEntry"\];/,
  );
  assert.match(
    canonicalized,
    /export type ArtifactRefInput = RuntimeApiComponents\["schemas"\]\["ArtifactRef-Input"\];/,
  );
  assert.match(canonicalized, /export type JsonValue = string \| number;/);
  assert.match(
    canonicalized,
    /export interface RuntimeApiClientOptions \{\n {2}baseUrl: string;\n\}/,
  );
});

test("canonicalization is byte-stable when replayed", () => {
  const schemaNames = [
    "AvailableGovernedProjectionPacket",
    "ChannelRegistryEntry",
    "ArtifactRef-Input",
  ];
  const first = canonicalizeRuntimeClientSource(GENERATED_SOURCE, schemaNames);
  const second = canonicalizeRuntimeClientSource(first, schemaNames);

  assert.equal(second, first);
});
