import type { ComponentType, ReactNode } from "react";
import type { LoaderFunction } from "react-router-dom";

import type { WorkspaceKey, WorkspacePrefetchKey } from "@/app/workspaces";
import type { SearchParamInput } from "@/lib/searchParams";

export type RouteSearchParser<TSearch> = (input: SearchParamInput) => TSearch;
export type RouteHrefBuilder<TSearch> = (input?: TSearch) => string;

export type AppRouteHandle<TSearch = unknown, THrefInput = Partial<TSearch>> = {
  buildHref: RouteHrefBuilder<THrefInput>;
  parseSearch: RouteSearchParser<TSearch>;
  prefetch?: WorkspacePrefetchKey[];
  routeId: string;
  workspaceKey?: WorkspaceKey;
};

export type AppRouteModule<TSearch = unknown, THrefInput = Partial<TSearch>> = {
  Component: ComponentType;
  errorElement?: ReactNode;
  handle: AppRouteHandle<TSearch, THrefInput>;
  index?: boolean;
  loader?: LoaderFunction;
  path?: string;
};
