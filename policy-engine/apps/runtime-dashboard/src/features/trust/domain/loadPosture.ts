import {
  admitClaimPostureRegister,
  type ClaimPostureRegister,
} from "./posture";

const POSTURE_ARTIFACT_PATH = "/atlas/trust-claim-posture.v1.json";

type FetchPosture = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export type PostureLoadResult =
  | Readonly<{
      status: "available";
      register: ClaimPostureRegister;
      rawBytes: Uint8Array;
    }>
  | Readonly<{
      status: "unavailable";
      reason:
        | "fetch_failed"
        | "http_error"
        | "empty_response"
        | "invalid_encoding"
        | "invalid_artifact";
    }>;

/** Load and strictly admit the public posture artifact without retaining state. */
export async function loadPosture(
  fetchPosture: FetchPosture = globalThis.fetch.bind(globalThis),
): Promise<PostureLoadResult> {
  let response: Response;
  try {
    response = await fetchPosture(POSTURE_ARTIFACT_PATH, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch {
    return { status: "unavailable", reason: "fetch_failed" };
  }

  if (!response.ok) {
    return { status: "unavailable", reason: "http_error" };
  }

  let capturedBytes: Uint8Array;
  try {
    const responseBuffer = await response.arrayBuffer();
    capturedBytes = new Uint8Array(responseBuffer).slice();
  } catch {
    return { status: "unavailable", reason: "fetch_failed" };
  }
  if (capturedBytes.byteLength === 0) {
    return { status: "unavailable", reason: "empty_response" };
  }

  let decoded: string;
  try {
    decoded = new TextDecoder("utf-8", { fatal: true }).decode(capturedBytes);
  } catch {
    return { status: "unavailable", reason: "invalid_encoding" };
  }

  let candidate: unknown;
  try {
    candidate = JSON.parse(decoded) as unknown;
  } catch {
    return { status: "unavailable", reason: "invalid_artifact" };
  }
  const admitted = await admitClaimPostureRegister(candidate);
  if (admitted === null) {
    return { status: "unavailable", reason: "invalid_artifact" };
  }
  return {
    status: "available",
    register: admitted,
    rawBytes: capturedBytes,
  };
}
