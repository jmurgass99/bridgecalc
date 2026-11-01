import van, { type State } from "vanjs-core";

export function getEnvelopes({
  xStations,
  momentPosKNm,
  momentNegKNm,
  reactionMaxKN,
}: {
  xStations: State<number[]>;
  momentPosKNm: State<number[]>;
  momentNegKNm: State<number[]>;
  reactionMaxKN: State<number[]>;
}): HTMLElement {
  const wrap = document.createElement("div");
  wrap.style.display = "flex";
  wrap.style.flexDirection = "column";
  wrap.style.gap = "12px";

  const cMom = document.createElement("canvas");
  cMom.className = "bc-chart";
  const cReac = document.createElement("canvas");
  cReac.className = "bc-chart";

  const makeCard = (t: string, c: HTMLCanvasElement) => {
    const d = document.createElement("div");
    d.className = "bc-card";
    const h = document.createElement("h3");
    h.textContent = t;
    d.append(h, c);
    return d;
  };

  wrap.append(
    makeCard("Envolvente de Momentos M+(x) / M-(x) [kN·m]", cMom),
    makeCard("Reacciones Máximas en Pilas y Estribos [kN]", cReac),
  );

  van.derive(() => {
    const xs = xStations.val;
    const mp = momentPosKNm.val;
    const mn = momentNegKNm.val;
    const ctx1 = cMom.getContext("2d");
    if (ctx1 && xs.length > 1) {
      const w = (cMom.width = cMom.clientWidth || 320);
      const h = (cMom.height = cMom.clientHeight || 155);
      ctx1.clearRect(0, 0, w, h);
      const maxX = xs[xs.length - 1] || 1;
      const maxM = Math.max(...mp, ...mn.map(Math.abs), 1) * 1.15;
      const y0 = h / 2;

      ctx1.strokeStyle = "rgba(148,163,184,0.3)";
      ctx1.beginPath();
      ctx1.moveTo(20, y0);
      ctx1.lineTo(w - 10, y0);
      ctx1.stroke();

      // M+ curve
      ctx1.strokeStyle = "#10b981";
      ctx1.lineWidth = 1.8;
      ctx1.beginPath();
      xs.forEach((x, i) => {
        const px = 20 + (x / maxX) * (w - 30);
        const py = y0 - (mp[i] / maxM) * (h * 0.42);
        if (i === 0) ctx1.moveTo(px, py);
        else ctx1.lineTo(px, py);
      });
      ctx1.stroke();

      // M- curve
      ctx1.strokeStyle = "#f43f5e";
      ctx1.beginPath();
      xs.forEach((x, i) => {
        const px = 20 + (x / maxX) * (w - 30);
        const py = y0 - (mn[i] / maxM) * (h * 0.42);
        if (i === 0) ctx1.moveTo(px, py);
        else ctx1.lineTo(px, py);
      });
      ctx1.stroke();
    }

    const ctx2 = cReac.getContext("2d");
    const r = reactionMaxKN.val;
    if (ctx2 && r.length > 0) {
      const w = (cReac.width = cReac.clientWidth || 320);
      const h = (cReac.height = cReac.clientHeight || 155);
      ctx2.clearRect(0, 0, w, h);
      const maxR = Math.max(...r, 1);
      r.forEach((val, idx) => {
        const bw = (w - 40) / r.length - 12;
        const x = 25 + idx * (bw + 12);
        const bh = ((h - 38) * val) / maxR;
        ctx2.fillStyle = "#38bdf8";
        ctx2.fillRect(x, h - 22 - bh, bw, bh);
        ctx2.fillStyle = "#f8fafc";
        ctx2.font = "10px Inter, sans-serif";
        ctx2.fillText(`P${idx}: ${val.toFixed(0)}`, x, h - 7);
      });
    }
  });

  return wrap;
}
