declare const interactionControlBrand: unique symbol;
declare const layoutGeometryBrand: unique symbol;
declare const motionGeometryBrand: unique symbol;
declare const operationalRequestControlBrand: unique symbol;

export type InteractionControl = number & {
  readonly [interactionControlBrand]: true;
};

export type LayoutGeometry = number & {
  readonly [layoutGeometryBrand]: true;
};

export type MotionGeometry = number & {
  readonly [motionGeometryBrand]: true;
};

export type OperationalRequestControl = number & {
  readonly [operationalRequestControlBrand]: true;
};

export function interactionControl(value: number): InteractionControl {
  return value as InteractionControl;
}

export function layoutGeometry(value: number): LayoutGeometry {
  return value as LayoutGeometry;
}

export function motionGeometry(value: number): MotionGeometry {
  return value as MotionGeometry;
}

export function operationalRequestControl(
  value: number,
): OperationalRequestControl {
  return value as OperationalRequestControl;
}
