/**
 * @typedef {{ projections: unknown[] }} ProjectionCatalog
 * @typedef {{ listGovernedProjections: () => Promise<ProjectionCatalog> }} ProjectionCatalogClient
 * @typedef {{ status: "available"; projectionCount: number }} AvailableProof
 * @typedef {{ status: "unavailable"; reason: string }} UnavailableProof
 */

/**
 * Exercise the shared generated client's governed-projection catalog operation.
 *
 * @param {ProjectionCatalogClient} client Shared generated runtime API client.
 * @returns {Promise<AvailableProof | UnavailableProof>} Proof result for shell rendering.
 */
export async function verifyGovernedProjectionCatalog(client) {
  try {
    const catalog = await client.listGovernedProjections();
    return {
      status: "available",
      projectionCount: catalog.projections.length,
    };
  } catch (error) {
    return {
      status: "unavailable",
      reason: String(error),
    };
  }
}
