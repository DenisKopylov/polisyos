/** Attack fixture: reproduce the retired public browser hash over arbitrary content. */
export function forgeLegacyPublicDecisionUrl(packet: unknown): string {
  function stableJson(value: unknown): string {
    if (Array.isArray(value)) {
      return `[${value.map(stableJson).join(",")}]`;
    }
    if (value && typeof value === "object") {
      return `{${Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, nested]) => `${JSON.stringify(key)}:${stableJson(nested)}`)
        .join(",")}}`;
    }
    return JSON.stringify(value);
  }

  const source = `polisyos.atlas.public-viewer.v1:${stableJson(packet)}`;
  let hash = 0x811c9dc5;
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  const suffix = (hash >>> 0).toString(16).padStart(8, "0");
  const bytes = new TextEncoder().encode(
    stableJson({ packet, signature: `sig:${suffix}` }),
  );
  const payload = btoa(
    Array.from(bytes, (byte) => String.fromCharCode(byte)).join(""),
  )
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/u, "");
  return `/public/decisions/${payload}.${suffix}`;
}
