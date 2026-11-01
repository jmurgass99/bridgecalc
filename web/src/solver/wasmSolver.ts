import type { BridgeEnvelopeResult, BridgeMesh } from "../data-model";

const BRIDGE_WASM_BASE64 =
  "AGFzbQEAAAABDgJgAnx8AXxgA3x8fAF8AwMCAAEHMAIUaGw5M1NpbXBsZVNwYW5Nb21lbnQAABViZWFtRmxleHVyYWxTdGlmZm5lc3MAAQo+AiEAIAFEAAAAAACAVkAgAKKiRJqZmZmZmfI/IACiIACioAsaAEQAAAAAAAAoQCAAoiABoiACIAKiIAKiows=";

export interface BridgeWasmExports {
  hl93SimpleSpanMoment: (L: number, impact: number) => number;
  beamFlexuralStiffness: (E: number, I: number, L: number) => number;
}

let cached: BridgeWasmExports | null = null;

function decode(b64: string): Uint8Array {
  if (typeof Buffer !== "undefined") return new Uint8Array(Buffer.from(b64, "base64"));
  const s = atob(b64);
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

export async function initBridgeWasm(): Promise<BridgeWasmExports> {
  if (cached) return cached;
  const bytes = decode(BRIDGE_WASM_BASE64);
  const { instance } = await WebAssembly.instantiate(bytes.buffer as ArrayBuffer);
  cached = instance.exports as unknown as BridgeWasmExports;
  return cached;
}

export function getBridgeWasmSync(): BridgeWasmExports {
  if (cached) return cached;
  const bytes = decode(BRIDGE_WASM_BASE64);
  const mod = new WebAssembly.Module(bytes.buffer as ArrayBuffer);
  const instance = new WebAssembly.Instance(mod);
  cached = instance.exports as unknown as BridgeWasmExports;
  return cached;
}

export function solveBridgeEnvelopeWasm({
  mesh,
  spanM,
  nSpans,
  impactFactor,
}: {
  mesh: BridgeMesh;
  spanM: number;
  nSpans: number;
  impactFactor: number;
}): BridgeEnvelopeResult {
  const wasm = getBridgeWasmSync();
  const m0 = wasm.hl93SimpleSpanMoment(spanM, impactFactor);

  const momentPosKNm: number[] = [];
  const momentNegKNm: number[] = [];

  for (const x of mesh.nodesX) {
    const spanIdx = Math.min(Math.floor(x / spanM), nSpans - 1);
    const xi = (x - spanIdx * spanM) / spanM;
    const parabola = 4 * xi * (1 - xi);
    const continuityFactor = nSpans > 1 ? 0.82 : 1.0;
    const mPos = m0 * continuityFactor * parabola;

    // Negative moment envelope peaks over interior piers (90% two-truck rule AASHTO §3.6.1.3.1)
    let mNeg = 0;
    for (let p = 1; p < nSpans; p++) {
      const xp = p * spanM;
      const distRatio = Math.abs(x - xp) / spanM;
      if (distRatio <= 1.0) {
        const pierPeak = -0.68 * m0 * Math.pow(1 - distRatio, 1.85);
        if (pierPeak < mNeg) mNeg = pierPeak;
      }
    }
    momentPosKNm.push(Number(mPos.toFixed(2)));
    momentNegKNm.push(Number(mNeg.toFixed(2)));
  }

  const reactionMaxKN: number[] = [];
  const vBase = (320 * impactFactor + 9.3 * spanM) * 0.65;
  for (let s = 0; s <= nSpans; s++) {
    const isInterior = s > 0 && s < nSpans;
    reactionMaxKN.push(Number((isInterior ? 1.85 * vBase : vBase).toFixed(2)));
  }

  return {
    engine: "wasm-local",
    xStations: mesh.nodesX,
    momentPosKNm,
    momentNegKNm,
    reactionMaxKN,
    maxPosMomentKNm: Math.max(...momentPosKNm, 0),
    minNegMomentKNm: Math.min(...momentNegKNm, 0),
  };
}
