export { renderArtifactViewer } from "@/features/artifacts/components/ArtifactViewerRegistry";
export { default } from "@/features/artifacts/routes/ArtifactInspectorPage";
export {
  buildArtifactHref,
  parseArtifactSearchParams,
} from "@/features/artifacts/domain/searchParams";
export type { ArtifactTab } from "@/features/artifacts/domain/searchParams";
export {
  artifactRoute,
  artifactRouteHandle,
  artifactRouteModule,
} from "./route";
