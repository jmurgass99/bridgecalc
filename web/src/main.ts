import van from "vanjs-core";
import type { BridgeMesh } from "./data-model";
import { getBridgeMesh } from "./mesh/getMesh";
import { runHybridBridgeEnvelope } from "./solver/apiClient";
import { initBridgeWasm } from "./solver/wasmSolver";
import { getEnvelopes } from "./ui/getEnvelopes";
import { getViewer3D } from "./viewer/getViewer3D";

const { div, h2, h3, input, label, option, select, span } = van.tags;

await initBridgeWasm();

const spanM = van.state(30);
const nSpans = van.state(3);
const divisionsPerSpan = van.state(10);
const impactFactor = van.state(1.33);
const truckPositionX = van.state(22);
const solverMode = van.state<"wasm-local" | "fastapi-python">("wasm-local");

const mesh = van.state<BridgeMesh>(
  getBridgeMesh(spanM.val, nSpans.val, divisionsPerSpan.val),
);
const xStations = van.state<number[]>([]);
const momentPosKNm = van.state<number[]>([]);
const momentNegKNm = van.state<number[]>([]);
const reactionMaxKN = van.state<number[]>([]);
const maxPosM = van.state(0);
const minNegM = van.state(0);

van.derive(() => {
  mesh.val = getBridgeMesh(spanM.val, nSpans.val, divisionsPerSpan.val);
});

van.derive(() => {
  runHybridBridgeEnvelope({
    mode: solverMode.val,
    apiUrl: "http://127.0.0.1:8000",
    mesh: mesh.val,
    spanM: spanM.val,
    nSpans: nSpans.val,
    impactFactor: impactFactor.val,
  }).then((res) => {
    xStations.val = res.xStations;
    momentPosKNm.val = res.momentPosKNm;
    momentNegKNm.val = res.momentNegKNm;
    reactionMaxKN.val = res.reactionMaxKN;
    maxPosM.val = res.maxPosMomentKNm;
    minNegM.val = res.minNegMomentKNm;
  });
});

const left = div(
  { class: "bc-panel" },
  h2({ style: "font-size: 1.05rem;" }, "BridgeCalc 3D — Tablero Continuo HL-93"),
  div(
    { class: "bc-card" },
    h3("Malla Semántica (supportToNodes / spanToElements)"),
    div(
      { class: "bc-row" },
      label("Luz por vano L [m]:"),
      input({
        type: "number",
        min: "10",
        max: "80",
        value: () => String(spanM.val),
        oninput: (e: Event) => (spanM.val = Math.max(10, Number((e.target as HTMLInputElement).value) || 25)),
      }),
    ),
    div(
      { class: "bc-row" },
      label("Número de vanos:"),
      input({
        type: "number",
        min: "1",
        max: "6",
        value: () => String(nSpans.val),
        oninput: (e: Event) => (nSpans.val = Math.max(1, Math.min(6, Number((e.target as HTMLInputElement).value) || 2))),
      }),
    ),
    div(
      { class: "bc-row" },
      label("Divisiones / vano:"),
      input({
        type: "number",
        min: "4",
        max: "24",
        value: () => String(divisionsPerSpan.val),
        oninput: (e: Event) => (divisionsPerSpan.val = Math.max(4, Number((e.target as HTMLInputElement).value) || 10)),
      }),
    ),
    div(
      { class: "bc-row" },
      label("Estaciones / Elementos:"),
      span(() => `${mesh.val.nodesX.length} / ${mesh.val.elements.length}`),
    ),
  ),
  div(
    { class: "bc-card" },
    h3("Camión de Diseño HL-93 (AASHTO LRFD)"),
    div(
      { class: "bc-row" },
      label("Posición Camión x [m]:"),
      input({
        type: "range",
        min: "0",
        max: () => String(spanM.val * nSpans.val),
        value: () => String(truckPositionX.val),
        oninput: (e: Event) => (truckPositionX.val = Number((e.target as HTMLInputElement).value)),
      }),
    ),
    div(
      { class: "bc-row" },
      label("Factor Impacto IM:"),
      input({
        type: "number",
        step: "0.05",
        value: () => String(impactFactor.val),
        oninput: (e: Event) => (impactFactor.val = Math.max(1.0, Number((e.target as HTMLInputElement).value) || 1.33)),
      }),
    ),
    div(
      { class: "bc-row" },
      label("Motor:"),
      select(
        {
          onchange: (e: Event) =>
            (solverMode.val = (e.target as HTMLSelectElement).value as "wasm-local" | "fastapi-python"),
        },
        option({ value: "wasm-local" }, "WASM Local (bridgeSolver)"),
        option({ value: "fastapi-python" }, "FastAPI Python"),
      ),
    ),
    div(
      { class: "bc-row" },
      label("M+ máx / M- mín:"),
      span(() => `+${maxPosM.val.toFixed(0)} / ${minNegM.val.toFixed(0)} kN·m`),
    ),
  ),
);

const right = div(
  { class: "bc-panel right" },
  getEnvelopes({
    xStations,
    momentPosKNm,
    momentNegKNm,
    reactionMaxKN,
  }),
);

document.body.appendChild(
  div(
    { class: "bc-layout" },
    left,
    getViewer3D({
      mesh,
      spanM,
      nSpans,
      truckPositionX,
      momentPosKNm,
    }),
    right,
  ),
);
