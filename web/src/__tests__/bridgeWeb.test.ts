import assert from "node:assert/strict";
import { getBridgeMesh } from "../mesh/getMesh.ts";
import { initBridgeWasm, solveBridgeEnvelopeWasm } from "../solver/wasmSolver.ts";

// 1. Mesh mapping
const m = getBridgeMesh(30, 3, 8);
assert.equal(m.nodesX.length, 25);
assert.equal(m.elements.length, 24);
assert.equal(m.geometryMapping.supportToNodes.get(1), 8);
assert.equal(m.geometryMapping.spanToElements.get(2)?.length, 8);

// 2. HL-93 envelope in WASM
await initBridgeWasm();
const m10 = getBridgeMesh(30, 3, 10);
const res = solveBridgeEnvelopeWasm({
  mesh: m10,
  spanM: 30,
  nSpans: 3,
  impactFactor: 1.33,
});

assert.ok(res.maxPosMomentKNm > 2000);
assert.ok(res.minNegMomentKNm < -1000);
assert.equal(res.reactionMaxKN.length, 4);

console.log(
  `BridgeCalc WASM test OK: M_pos_max=${res.maxPosMomentKNm.toFixed(1)} kN·m, M_neg_min=${res.minNegMomentKNm.toFixed(1)} kN·m`
);
