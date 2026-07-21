import type {
  CounterfactualMetric as RuntimeCounterfactualMetric,
  FabricDecisionData as RuntimeFabricDecisionData,
  FabricDecisionDataResponse as RuntimeFabricDecisionDataResponse,
  LineageBatchResponse as RuntimeLineageBatchResponse,
  LineageCompactSummaryItem as RuntimeLineageCompactSummaryItem,
  LineageExportLinks as RuntimeLineageExportLinks,
  LineageExportResponse as RuntimeLineageExportResponse,
  LineageGraphEdge as RuntimeLineageGraphEdge,
  LineageGraphNode as RuntimeLineageGraphNode,
  LineageGraphView as RuntimeLineageGraphView,
  LineageResponse as RuntimeLineageResponse,
  PolisyosCoreContractsRuntimeLineageRefOutput as RuntimeLineageRef,
  QuantityUncertainty as RuntimeQuantityUncertainty,
  QuantityValueOutput as RuntimeQuantityValue,
  ScenarioRef as RuntimeScenarioRef,
  polisyos__core__contracts__runtime__TemporalRef as RuntimeTemporalRef,
  polisyos__core__contracts__runtime__UnitRef as RuntimeUnitRef,
} from "@polisyos/runtime-api-client";

export type CounterfactualMetric = RuntimeCounterfactualMetric;
export type FabricDecisionData = RuntimeFabricDecisionData;
export type FabricDecisionDataResponse = RuntimeFabricDecisionDataResponse;
export type LineageBatchResponsePayload = RuntimeLineageBatchResponse;
export type LineageCompactSummaryItem = RuntimeLineageCompactSummaryItem;
export type LineageExportLinks = RuntimeLineageExportLinks;
export type LineageExportPayload = RuntimeLineageExportResponse;
export type LineageGraphEdge = RuntimeLineageGraphEdge;
export type LineageGraphNode = RuntimeLineageGraphNode;
export type LineageGraphView = RuntimeLineageGraphView;
export type LineageRef = RuntimeLineageRef;
export type LineageResponsePayload = RuntimeLineageResponse;
export type QuantityUncertainty = RuntimeQuantityUncertainty;
export type QuantityValue = RuntimeQuantityValue;
export type ScenarioRef = RuntimeScenarioRef;
export type TemporalRef = RuntimeTemporalRef;
export type UnitRef = RuntimeUnitRef;

export type LineageFreshness = LineageRef["freshness"];
export type QuantityClass = QuantityValue["quantity_class"];
export type VerificationStatus = LineageRef["status"];
