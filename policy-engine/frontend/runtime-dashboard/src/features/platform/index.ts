export { default } from "@/features/platform/routes/PlatformHealthPage";
export {
  buildPlatformHref,
  parsePlatformSearchParams,
} from "./domain/searchParams";
export type { PlatformSearchParams } from "./domain/searchParams";
export {
  platformLoader,
  platformRoute,
  platformRouteHandle,
  platformRouteModule,
} from "./route";
