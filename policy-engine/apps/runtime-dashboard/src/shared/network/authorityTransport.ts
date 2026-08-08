/** Issue type-preserving inputs for the bounded native authority transports. */

declare const purposeBrand: unique symbol;
declare const inputBrand: unique symbol;

type TransportPurposeName =
  | "auth"
  | "flag_exposure"
  | "telemetry"
  | "governed_channel";
type FetchPurposeName = Exclude<TransportPurposeName, "governed_channel">;

export type TransportPurpose<Name extends TransportPurposeName> = {
  readonly name: Name;
  readonly [purposeBrand]: Name;
};

type TransportInput<
  Name extends TransportPurposeName,
  Input extends RequestInfo | URL,
> = Input & {
  readonly [inputBrand]: Name;
};

function issuePurpose<Name extends TransportPurposeName>(
  name: Name,
): TransportPurpose<Name> {
  return { name } as TransportPurpose<Name>;
}

function bindInput<
  Name extends TransportPurposeName,
  Input extends RequestInfo | URL,
>(
  purpose: TransportPurpose<Name>,
  input: Input,
): TransportInput<Name, Input> {
  void purpose;
  return input as TransportInput<Name, Input>;
}

export const authorityTransportPurpose = {
  auth: issuePurpose("auth"),
  flag_exposure: issuePurpose("flag_exposure"),
  telemetry: issuePurpose("telemetry"),
  governed_channel: issuePurpose("governed_channel"),
} as const;

export function bindFetchAuthorityInput<
  Name extends FetchPurposeName,
  Input extends RequestInfo | URL,
>(
  purpose: TransportPurpose<Name>,
  input: Input,
): TransportInput<Name, Input> {
  return bindInput(purpose, input);
}

export function bindEventSourceAuthorityInput<Input extends string>(
  purpose: TransportPurpose<"governed_channel">,
  input: Input,
): TransportInput<"governed_channel", Input> {
  return bindInput(purpose, input);
}

export function bindWebSocketAuthorityInput<Input extends string>(
  purpose: TransportPurpose<"governed_channel">,
  input: Input,
): TransportInput<"governed_channel", Input> {
  return bindInput(purpose, input);
}
