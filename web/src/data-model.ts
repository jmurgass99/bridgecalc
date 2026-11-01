export interface BridgeGeometryMapping {
  supportToNodes: Map<number, number>;
  spanToElements: Map<number, number[]>;
}

export interface BridgeMesh {
  nodesX: number[];
  elements: [number, number][];
  geometryMapping: BridgeGeometryMapping;
}

export interface BridgeEnvelopeResult {
  engine: "wasm-local" | "fastapi-python";
  xStations: number[];
  momentPosKNm: number[];
  momentNegKNm: number[];
  reactionMaxKN: number[];
  maxPosMomentKNm: number;
  minNegMomentKNm: number;
}
