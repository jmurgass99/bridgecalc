import type { BridgeMesh } from "../data-model.ts";

export function getBridgeMesh(
  spanM: number,
  nSpans: number,
  divisionsPerSpan: number,
): BridgeMesh {
  const nDiv = Math.max(2, Math.floor(divisionsPerSpan));
  const supportToNodes = new Map<number, number>();
  const spanToElements = new Map<number, number[]>();
  const nodesX: number[] = [];
  const elements: [number, number][] = [];

  for (let s = 0; s < nSpans; s++) {
    const x0 = s * spanM;
    if (s === 0) {
      supportToNodes.set(0, 0);
      nodesX.push(0);
    }
    const elemIds: number[] = [];
    for (let k = 1; k <= nDiv; k++) {
      const xk = Number((x0 + (k / nDiv) * spanM).toFixed(5));
      const nPrev = nodesX.length - 1;
      nodesX.push(xk);
      const nCurr = nodesX.length - 1;
      elemIds.push(elements.length);
      elements.push([nPrev, nCurr]);
    }
    supportToNodes.set(s + 1, nodesX.length - 1);
    spanToElements.set(s + 1, elemIds);
  }

  return {
    nodesX,
    elements,
    geometryMapping: { supportToNodes, spanToElements },
  };
}
