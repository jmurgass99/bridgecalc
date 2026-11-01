import * as THREE from "three";
import van, { type State } from "vanjs-core";
import type { BridgeMesh } from "../data-model";

export function getViewer3D({
  mesh,
  spanM,
  nSpans,
  truckPositionX,
  momentPosKNm,
}: {
  mesh: State<BridgeMesh>;
  spanM: State<number>;
  nSpans: State<number>;
  truckPositionX: State<number>;
  momentPosKNm: State<number[]>;
}): HTMLElement {
  const container = document.createElement("div");
  container.className = "bc-viewer";

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  container.appendChild(renderer.domElement);

  const group = new THREE.Group();
  scene.add(group);

  van.derive(() => {
    while (group.children.length > 0) group.remove(group.children[0]);
    const m = mesh.val;
    const totalL = spanM.val * nSpans.val;
    const truckX = truckPositionX.val;
    const mPos = momentPosKNm.val;

    camera.position.set(totalL * 0.5, -totalL * 0.85, totalL * 0.28);
    camera.up.set(0, 0, 1);
    camera.lookAt(totalL * 0.5, 0, 0);

    // Bridge deck segments mapped via spanToElements
    const maxM = Math.max(...mPos, 1);
    for (const [, elemIds] of m.geometryMapping.spanToElements.entries()) {
      for (const eIdx of elemIds) {
        const [na, nb] = m.elements[eIdx];
        const xa = m.nodesX[na];
        const xb = m.nodesX[nb];
        const len = xb - xa;
        const ratio = (mPos[na] ?? 0) / maxM;
        const geom = new THREE.BoxGeometry(len * 0.96, 3.6, 0.7);
        const mat = new THREE.MeshBasicMaterial({
          color: new THREE.Color().setHSL(0.56 - ratio * 0.45, 0.85, 0.52),
        });
        const box = new THREE.Mesh(geom, mat);
        box.position.set(0.5 * (xa + xb), 0, 0);
        group.add(box);
      }
    }

    // Piers mapped via supportToNodes
    const pierGeom = new THREE.CylinderGeometry(0.55, 0.7, 6, 16);
    const pierMat = new THREE.MeshBasicMaterial({ color: 0x94a3b8, wireframe: true });
    for (const [, nodeIdx] of m.geometryMapping.supportToNodes.entries()) {
      const xp = m.nodesX[nodeIdx] ?? 0;
      const pier = new THREE.Mesh(pierGeom, pierMat);
      pier.rotation.x = Math.PI / 2;
      pier.position.set(xp, 0, -3.35);
      group.add(pier);
    }

    // HL-93 3-axle moving design truck (35 kN, 145 kN, 145 kN spaced at 4.3 m)
    const axleOffsets = [0, -4.3, -8.6];
    const axleGeom = new THREE.BoxGeometry(1.1, 2.2, 1.2);
    const axleMat = new THREE.MeshBasicMaterial({ color: 0xf43f5e });
    for (const off of axleOffsets) {
      const ax = truckX + off;
      if (ax >= 0 && ax <= totalL) {
        const meshAx = new THREE.Mesh(axleGeom, axleMat);
        meshAx.position.set(ax, 0, 1.0);
        group.add(meshAx);
      }
    }

    renderer.render(scene, camera);
  });

  const ro = new ResizeObserver(() => {
    const w = container.clientWidth || 700;
    const h = container.clientHeight || 500;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
    renderer.render(scene, camera);
  });
  ro.observe(container);

  return container;
}
