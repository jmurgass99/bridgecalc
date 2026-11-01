import { describe, expect, it } from "vitest";
import { getBridgeMesh } from "../mesh/getMesh";
import { initBridgeWasm, solveBridgeEnvelopeWasm } from "../solver/wasmSolver";

describe("BridgeCalc Web — GeometryMapping + bridgeSolver.wasm", () => {
  it("maps supports and spans across mesh divisions", () => {
    const m = getBridgeMesh(30, 3, 8);
    expect(m.nodesX.length).toBe(25);
    expect(m.elements.length).toBe(24);
    expect(m.geometryMapping.supportToNodes.get(1)).toBe(8);
    expect(m.geometryMapping.spanToElements.get(2)?.length).toBe(8);
  });

  it("evaluates HL-93 envelope via WebAssembly", async () => {
    await initBridgeWasm();
    const m = getBridgeMesh(30, 3, 10);
    const res = solveBridgeEnvelopeWasm({
      mesh: m,
      spanM: 30,
      nSpans: 3,
      impactFactor: 1.33,
    });
    expect(res.maxPosMomentKNm).toBeGreaterThan(2000);
    expect(res.minNegMomentKNm).toBeLessThan(-1000);
    expect(res.reactionMaxKN.length).toBe(4);
  });
});
