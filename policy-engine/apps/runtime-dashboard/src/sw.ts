/// <reference lib="webworker" />

import { clientsClaim } from "workbox-core";
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";

declare let self: ServiceWorkerGlobalScope;

const OFFLINE_QUEUE_SYNC_TAG = "runtime-dashboard-offline-queue";
type SyncEventLike = ExtendableEvent & { tag: string };

self.skipWaiting();
clientsClaim();
cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

registerRoute(
  new NavigationRoute(createHandlerBoundToURL("/index.html"), {
    denylist: [/^\/api\//, /^\/health$/, /^\/ready$/],
  }),
);

async function notifyOfflineQueueFlush() {
  const windowClients = await self.clients.matchAll({ type: "window" });
  for (const client of windowClients) {
    client.postMessage({ type: "offline-queue:flush" });
  }
}

self.addEventListener("activate", (event) => {
  event.waitUntil(notifyOfflineQueueFlush());
});

self.addEventListener("sync", (event: Event) => {
  const syncEvent = event as SyncEventLike;
  if (syncEvent.tag !== OFFLINE_QUEUE_SYNC_TAG) {
    return;
  }

  syncEvent.waitUntil(notifyOfflineQueueFlush());
});
