export type CategoricalPattern =
  | "solid"
  | "diagonal"
  | "cross"
  | "dot"
  | "dash"
  | "ring";

export type CategoricalPaletteSwatch = {
  name: string;
  color: string;
  highContrastColor: string;
  pattern: CategoricalPattern;
  shape: "circle" | "square" | "triangle" | "diamond" | "line" | "plus";
};

export const categorical8 = [
  {
    name: "teal",
    color: "#00796b",
    highContrastColor: "CanvasText",
    pattern: "solid",
    shape: "circle",
  },
  {
    name: "ember",
    color: "#b44a2f",
    highContrastColor: "Mark",
    pattern: "diagonal",
    shape: "square",
  },
  {
    name: "gold",
    color: "#8f6b10",
    highContrastColor: "CanvasText",
    pattern: "dot",
    shape: "triangle",
  },
  {
    name: "plum",
    color: "#76528a",
    highContrastColor: "CanvasText",
    pattern: "cross",
    shape: "diamond",
  },
  {
    name: "olive",
    color: "#65732d",
    highContrastColor: "CanvasText",
    pattern: "dash",
    shape: "line",
  },
  {
    name: "lagoon",
    color: "#1f7a8c",
    highContrastColor: "LinkText",
    pattern: "ring",
    shape: "plus",
  },
  {
    name: "rose",
    color: "#a54d68",
    highContrastColor: "CanvasText",
    pattern: "diagonal",
    shape: "circle",
  },
  {
    name: "graphite",
    color: "#40515f",
    highContrastColor: "CanvasText",
    pattern: "cross",
    shape: "square",
  },
] as const satisfies readonly CategoricalPaletteSwatch[];

export const categorical12 = [
  ...categorical8,
  {
    name: "copper",
    color: "#c46f2d",
    highContrastColor: "Mark",
    pattern: "dot",
    shape: "diamond",
  },
  {
    name: "moss",
    color: "#3f7d4c",
    highContrastColor: "CanvasText",
    pattern: "dash",
    shape: "triangle",
  },
  {
    name: "indigo",
    color: "#5867a8",
    highContrastColor: "CanvasText",
    pattern: "ring",
    shape: "line",
  },
  {
    name: "clay",
    color: "#8a6e54",
    highContrastColor: "CanvasText",
    pattern: "solid",
    shape: "plus",
  },
] as const satisfies readonly CategoricalPaletteSwatch[];

export function categoricalSwatch(index: number, size: 8 | 12 = 12) {
  const palette = size === 8 ? categorical8 : categorical12;
  return palette[((index % palette.length) + palette.length) % palette.length];
}

export function categoricalCssVars(prefix = "category") {
  return Object.fromEntries(
    categorical12.map((swatch, index) => [
      `--${prefix}-${index + 1}`,
      swatch.color,
    ]),
  ) as Record<string, string>;
}
