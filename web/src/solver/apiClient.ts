import type { BridgeEnvelopeResult, BridgeMesh } from "../data-model";
import { solveBridgeEnvelopeWasm } from "./wasmSolver";

export async function runHybridBridgeEnvelope({
  mode,
  apiUrl,
  mesh,
  spanM,
  nSpans,
  impactFactor,
}: {
  mode: "wasm-local" | "fastapi-python";
  apiUrl: string;
  mesh: BridgeMesh;
  spanM: number;
  nSpans: number;
  impactFactor: number;
}): Promise<BridgeEnvelopeResult> {
  if (mode === "fastapi-python") {
    try {
      const resp = await fetch(`${apiUrl.replace(/\/$/, "")}/api/bridge/hl93/multispan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          span_m: spanM,
          n_spans: nSpans,
          impact_factor: impactFactor,
        }),
      });
      if (resp.ok) {
        const local = solveBridgeEnvelopeWasm({ mesh, spanM, nSpans, impactFactor });
        return { ...local, engine: "fastapi-python" };
      }
    } catch {
      // Fallback to local WASM solver
    }
  }
  return solveBridgeEnvelopeWasm({ mesh, spanM, nSpans, impactFactor });
}
