import * as THREE from "three";
import { OrbitControls } from "/assets/vendor/OrbitControls.js";

const $ = (s) => document.querySelector(s);
const copy = (x) => JSON.parse(JSON.stringify(x));
const motionSignature = (value) => JSON.stringify([value.geometry_signature, value.document.metadata?.design_mechanism || null]);
const escape = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (x, d = 1) =>
  Number(x).toLocaleString(undefined, { maximumFractionDigits: d });
const specDefaults = {
  name: "Foldable enclosure",
  inner_width_mm: 90,
  inner_depth_mm: 60,
  inner_height_mm: 45,
  thickness_mm: 3,
  material: "polypropylene",
  lid: false,
};
const reqDefaults = {
  min_capacity_l: 0.2,
  max_outer_width_mm: 160,
  max_outer_depth_mm: 120,
  max_outer_height_mm: 80,
  max_mass_kg: 1,
  lock_inner_dimensions: true,
  objective: "minimize_mass",
  payload_kg: 0,
  max_floor_deflection_mm: 3,
};
const specFields = [
  ["inner_width_mm", "Clear width", "mm"],
  ["inner_depth_mm", "Clear depth", "mm"],
  ["inner_height_mm", "Clear height", "mm"],
  ["thickness_mm", "Panel thickness", "mm"],
];
const reqFields = [
  ["min_capacity_l", "Minimum capacity", "L"],
  ["max_mass_kg", "Maximum mass", "kg"],
  ["max_outer_width_mm", "Maximum outside width", "mm"],
  ["max_outer_depth_mm", "Maximum outside depth", "mm"],
  ["max_outer_height_mm", "Maximum outside height", "mm"],
  ["payload_kg", "Payload for floor screening", "kg"],
  ["max_floor_deflection_mm", "Maximum floor deflection", "mm"],
];

export function createWorkflow(bridge) {
  let snapshot,
    revision,
    draftRevision,
    dirty = false,
    task = false,
    optionsContext = null,
    study = null,
    studyKey = null,
    angle = 0,
    playing = false,
    lastTime = 0,
    travel = 1;
  let renderer, scene, camera, controls, group;
  let zoom = 0.8,
    pan = null;
  const boardWidth = 3100,
    boardHeight = 760;
  $("#project-tab").innerHTML =
    `<div class="workflow-page"><div class="workflow-heading"><div><small>SHARED PROJECT</small><h1>Intent & requirements</h1><p id="project-binding">Loading project…</p></div><button id="project-reload">Reload saved values</button></div><form id="project-form"><div class="project-columns"><section class="project-card"><h2>Design brief</h2><label class="field-label">What are we designing?<textarea id="project-brief" rows="5" maxlength="6000" placeholder="Purpose, constraints and fabrication context"></textarea></label><label class="field-label">Project name<input id="project-name" maxlength="100" required></label><h2>Enclosure dimensions</h2><div id="project-spec-fields" class="project-fields"></div><label class="field-label">Material<select id="project-material"><option value="birch_plywood">Birch plywood</option><option value="polypropylene">Polypropylene</option><option value="aluminum">Aluminum</option><option value="steel">Steel</option></select></label><label class="project-check"><input type="checkbox" id="project-lid"> Include top panel</label></section><section class="project-card"><h2>Design requirements</h2><div id="project-req-fields" class="project-fields"></div><label class="field-label">Objective<select id="project-objective"><option value="minimize_mass">Minimum mass</option><option value="maximize_capacity">Maximum capacity</option></select></label><label class="project-check"><input type="checkbox" id="project-lock"> Lock internal dimensions during optimization</label><p class="workflow-scope">Reference material properties. Floor screening uses an ideal beam model; joining details and tolerances need review.</p></section></div><div class="project-actions"><label id="project-replace-label" class="project-check"><input type="checkbox" id="project-replace"> Replace custom geometry with enclosure panels</label><button type="button" id="project-save-brief">Save brief only</button><button type="button" id="project-compare">Compare alternatives</button><button class="primary" id="project-apply">Rebuild & save revision</button></div><p id="project-message" role="status"></p></form><section id="project-options" class="hidden"><h2>Feasible alternatives</h2><p>Preview metrics below. Applying a choice regenerates panels and saves a revision.</p><div id="project-option-list" class="workflow-options"></div></section></div>`;
  const fields = (items, prefix) =>
    items
      .map(
        ([key, label, unit]) =>
          `<label class="field-label">${label} <span>${unit}</span><input id="${prefix}${key}" type="number" step="any" min="${key === "payload_kg" ? 0 : 0.001}" required></label>`,
      )
      .join("");
  $("#project-spec-fields").innerHTML = fields(specFields, "spec-");
  $("#project-req-fields").innerHTML = fields(reqFields, "req-");
  $("#motion-tab").innerHTML =
    `<div class="motion-layout"><div class="motion-heading"><div><small>FINITE-THICKNESS MOTION</small><h1>Wall folding</h1><p id="motion-state">Build an open enclosure in Project to begin.</p></div><div class="motion-heading-actions"><button id="motion-focus">Focus view</button><button id="motion-run" class="primary">Run motion study</button></div></div><div class="motion-settings"><label>Maximum angle <input id="motion-max" type="number" min="1" max="90" value="90"> °</label><label>Sample poses <select id="motion-samples"><option>19</option><option selected>37</option><option>73</option></select></label></div><div id="motion-viewport" aria-label="Interactive folding simulation"></div><div class="motion-controls"><button id="motion-play" disabled>▶ Play</button><label>Wall angle <input type="range" id="motion-angle" min="0" max="90" step="0.1" value="0" disabled></label><output id="motion-angle-label">0°</output><button id="motion-reset">Reset</button><button id="motion-fit">Fit</button><button id="motion-save" disabled>Save study settings</button></div><div class="motion-analysis"><div id="motion-metrics">Simulation is bound to the current enclosure definition.</div><details><summary>Study details</summary><svg id="motion-chart" viewBox="0 0 600 105" role="img" aria-label="Outside envelope through wall motion"></svg><p id="motion-scope">Virtual hinges, rigid panels and prescribed outward motion. Hardware and structural behavior require separate validation.</p></details></div></div>`;
  $("#motion-tab .motion-settings").insertAdjacentHTML("afterend", '<div id="motion-states" class="motion-states hidden" aria-label="Named mechanism states"></div>');
  $("#canvas-tab").innerHTML =
    `<div class="canvas-toolbar"><strong>Project canvas</strong><span id="canvas-revision"></span><button id="canvas-minus" aria-label="Zoom canvas out">−</button><output id="canvas-zoom">80%</output><button id="canvas-plus" aria-label="Zoom canvas in">＋</button><button id="canvas-fit">Fit all</button></div><div id="workflow-board" tabindex="0" aria-label="Project stage canvas; drag empty space to pan, wheel to zoom"><div id="workflow-world-size"><div id="workflow-world"><svg class="workflow-connectors" width="3100" height="760" aria-hidden="true"><path d="M 450 340 H 2740" stroke="#d3c7b5" stroke-width="2" fill="none" stroke-dasharray="6 6"/></svg><div id="workflow-cards"></div></div></div></div><div class="canvas-pip"><img id="canvas-pip-image" alt="Current CAD model overview"><span>Current revision</span></div><div id="canvas-map" aria-label="Canvas minimap"><div id="canvas-map-cards"></div><div id="canvas-map-view"></div></div><div class="canvas-hint">Drag background to pan · Wheel to zoom · Shift-wheel to scroll · Double-click a stage to open</div>`;

  function context() {
    return JSON.stringify({
      id: bridge.getState().snapshot?.id,
      document: bridge.getState().document,
    });
  }
  function message(text, error = false) {
    $("#project-message").textContent = text;
    $("#project-message").classList.toggle("error-note", error);
  }
  function formData() {
    const spec = {
      ...specDefaults,
      name: $("#project-name").value.trim(),
      material: $("#project-material").value,
      lid: $("#project-lid").checked,
    };
    specFields.forEach(
      ([key]) => (spec[key] = Number($("#spec-" + key).value)),
    );
    const requirements = {
      ...reqDefaults,
      objective: $("#project-objective").value,
      lock_inner_dimensions: $("#project-lock").checked,
    };
    reqFields.forEach(
      ([key]) => (requirements[key] = Number($("#req-" + key).value)),
    );
    return { spec, requirements };
  }
  function loadForm() {
    const meta = bridge.getState().document?.metadata || {};
    const spec = meta.source_spec || specDefaults,
      req = meta.source_requirements || reqDefaults;
    $("#project-brief").value = meta.brief || "";
    $("#project-name").value = spec.name;
    specFields.forEach(([key]) => ($("#spec-" + key).value = spec[key]));
    reqFields.forEach(([key]) => ($("#req-" + key).value = req[key]));
    $("#project-material").value = spec.material;
    $("#project-lid").checked = spec.lid;
    $("#project-objective").value = req.objective;
    $("#project-lock").checked = req.lock_inner_dimensions;
    $("#project-replace").checked = false;
    dirty = false;
    draftRevision = bridge.getState().snapshot?.id;
    optionsContext = null;
    $("#project-options").classList.add("hidden");
    message("");
  }
  async function runTask(action) {
    if (task || bridge.getState().busy) return;
    if (
      bridge.getState().pending ||
      bridge.getState().inspectorDirty ||
      bridge.getState().agentPreview
    ) {
      message(
        "Save or discard pending CAD edits before changing the shared project.",
        true,
      );
      return;
    }
    if (dirty && draftRevision !== bridge.getState().snapshot?.id) {
      message(
        "The base revision changed. Reload saved values before applying project settings.",
        true,
      );
      return;
    }
    task = true;
    const buttons = [
      ...$("#project-tab").querySelectorAll("button"),
      $("#motion-run"),
      $("#motion-save"),
    ];
    const inputs = [
      ...$("#project-form").querySelectorAll("input,textarea,select"),
      $("#motion-max"),
      $("#motion-samples"),
    ];
    buttons.forEach((b) => (b.disabled = true));
    inputs.forEach((input) => (input.disabled = true));
    try {
      await action();
    } catch (error) {
      message(error.message, true);
      bridge.toast(error.message, true);
    } finally {
      task = false;
      buttons.forEach((b) => (b.disabled = false));
      inputs.forEach((input) => (input.disabled = false));
      $("#motion-save").disabled = !study || !motionSettingsMatch();
    }
  }
  async function applyEnclosure(data) {
    const base = context(),
      doc = copy(bridge.getState().document);
    doc.metadata ||= {};
    doc.metadata.brief = $("#project-brief").value;
    const preview = await bridge.api("/enclosure/preview", {
      document: doc,
      ...data,
      replace_geometry: $("#project-replace").checked,
    });
    if (base !== context())
      throw new Error(
        "Project changed during rebuild. Reload the project values and try again.",
      );
    await bridge.save(
      preview.document,
      "Rebuild enclosure from project requirements",
    );
    dirty = false;
    loadForm();
    message(
      preview.requirements_state.passed
        ? "Saved revision. Geometry, drawings and requirements are current."
        : "Saved revision. Some requirements fail; review the checks before fabrication.",
      !preview.requirements_state.passed,
    );
  }
  $("#project-form").addEventListener("input", () => {
    if (!dirty) draftRevision = bridge.getState().snapshot?.id;
    dirty = true;
    optionsContext = null;
    $("#project-options").classList.add("hidden");
    message("Unsaved project settings");
  });
  $("#project-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    runTask(() => applyEnclosure(formData()));
  });
  $("#project-reload").onclick = loadForm;
  $("#project-save-brief").onclick = () =>
    runTask(async () => {
      const doc = copy(bridge.getState().document);
      doc.metadata ||= {};
      doc.metadata.brief = $("#project-brief").value;
      const result = await bridge.save(doc, "Update project brief");
      draftRevision = result.id;
      message("Brief saved. Other form settings remain unsaved.");
    });
  $("#project-compare").onclick = () =>
    runTask(async () => {
      if (!$("#project-form").reportValidity()) return;
      const base = context(),
        input = JSON.stringify(formData());
      const result = await bridge.api("/enclosure/options", {
        document: bridge.getState().document,
        ...formData(),
      });
      if (base !== context() || input !== JSON.stringify(formData()))
        throw new Error("Project changed during search. Compare again.");
      optionsContext = { base, input, candidates: result.candidates };
      $("#project-options").classList.remove("hidden");
      $("#project-option-list").innerHTML = result.candidates
        .map(
          (c, i) =>
            `<article class="project-card"><small>${i === 0 ? "RECOMMENDED" : "ALTERNATIVE " + i}</small><h3>${num(c.spec.thickness_mm)} mm stock</h3><p>${num(c.metrics.mass_kg, 2)} kg · ${num(c.metrics.capacity_l, 2)} L</p><p>${num(c.metrics.outer_width_mm)} × ${num(c.metrics.outer_depth_mm)} × ${num(c.metrics.outer_height_mm)} mm</p><button data-workflow-option="${i}">Apply & save revision</button></article>`,
        )
        .join("");
      message(
        `${result.evaluated_count} stock candidates checked · ${result.candidates.length} feasible in this search family.`,
      );
    });
  $("#project-option-list").onclick = (event) => {
    const b = event.target.closest("[data-workflow-option]");
    if (!b) return;
    runTask(async () => {
      if (
        !optionsContext ||
        optionsContext.base !== context() ||
        optionsContext.input !== JSON.stringify(formData())
      )
        throw new Error("Comparison is stale. Search again.");
      const c = optionsContext.candidates[Number(b.dataset.workflowOption)];
      await applyEnclosure({ spec: c.spec, requirements: c.requirements });
    });
  };

  function initMotion() {
    if (renderer) return;
    const host = $("#motion-viewport");
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    host.append(renderer.domElement);
    scene = new THREE.Scene();
    scene.background = new THREE.Color("#f5f2ec");
    camera = new THREE.PerspectiveCamera(40, 1, 0.1, 20000);
    camera.up.set(0, 0, 1);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x77716a, 2.5));
    const light = new THREE.DirectionalLight(0xffffff, 2);
    light.position.set(-300, -400, 700);
    scene.add(light);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    const grid = new THREE.GridHelper(2000, 80, 0xd6cdbf, 0xe4ddd2);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.1;
    scene.add(grid);
    new ResizeObserver(resizeMotion).observe(host);
    renderer.setAnimationLoop((time) => {
      if (!$("#motion-tab").classList.contains("active")) {
        lastTime = time;
        return;
      }
      if (playing && study) {
        const dt = Math.min((time - lastTime) / 1000, 0.05);
        angle += travel * dt * 22;
        if (angle >= (study.config.progress_max ?? study.config.max_angle_deg)) {
          angle = study.config.progress_max ?? study.config.max_angle_deg;
          travel = -1;
        }
        if (angle <= 0) {
          angle = 0;
          travel = 1;
        }
        updateAngle(angle);
      }
      lastTime = time;
      controls.update();
      renderer.render(scene, camera);
    });
  }
  function resizeMotion() {
    if (!renderer) return;
    const h = $("#motion-viewport");
    if (!h.clientWidth || !h.clientHeight) return;
    renderer.setSize(h.clientWidth, h.clientHeight, false);
    camera.aspect = h.clientWidth / h.clientHeight;
    camera.updateProjectionMatrix();
  }
  function fitMotion() {
    if (!study || !camera || !group) return;
    group.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(group);
    if (study?.family === "general_mechanism") study.frames.forEach(frame => {
      bounds.expandByPoint(new THREE.Vector3(...frame.bounds_mm[0]));
      bounds.expandByPoint(new THREE.Vector3(...frame.bounds_mm[1]));
    });
    const center = bounds.getCenter(new THREE.Vector3());
    const direction = new THREE.Vector3(0.75, -0.95, 0.8).normalize();
    const right = new THREE.Vector3()
      .crossVectors(direction, new THREE.Vector3(0, 0, 1))
      .normalize();
    const up = new THREE.Vector3().crossVectors(right, direction).normalize();
    const tan = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    let distance = 1;
    for (const x of [bounds.min.x, bounds.max.x])
      for (const y of [bounds.min.y, bounds.max.y])
        for (const z of [bounds.min.z, bounds.max.z]) {
          const point = new THREE.Vector3(x, y, z).sub(center);
          distance = Math.max(
            distance,
            point.dot(direction) +
              Math.max(
                Math.abs(point.dot(up)) / tan,
                Math.abs(point.dot(right)) / (tan * camera.aspect),
              ),
          );
        }
    const size = bounds.getSize(new THREE.Vector3()).length();
    controls.target.copy(center);
    camera.position.copy(center).addScaledVector(direction, distance * 1.18);
    camera.near = Math.max(0.05, size / 10000);
    camera.far = Math.max(1000, size * 30);
    camera.updateProjectionMatrix();
    controls.update();
  }
  function clearGroup() {
    if (!group) return;
    scene.remove(group);
    group.traverse((o) => {
      o.geometry?.dispose();
      if (o.material) [o.material].flat().forEach((m) => m.dispose());
    });
    group = null;
  }
  function displayStudy(value) {
    initMotion();
    clearGroup();
    study = value;
    group = new THREE.Group();
    if (value.family === "panel_hinges" || value.family === "general_mechanism") {
      value.parts.forEach((p,i) => {
        const geometry=new THREE.BufferGeometry();
        geometry.setAttribute("position",new THREE.Float32BufferAttribute(p.vertices,3));
        geometry.setIndex(p.triangles); geometry.computeVertexNormals();
        const color=p.kind==="pin" ? 0xa87a3e : [0xb7c9d1,0x91adb7,0xc8b89d][(p.face ?? i)%3];
        const mesh=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color,roughness:.65}));
        mesh.userData={part:p,baseColor:color};mesh.matrixAutoUpdate=false;
        mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geometry),new THREE.LineBasicMaterial({color:0x46565d,transparent:true,opacity:.45})));
        group.add(mesh);
      });
    } else value.panels.forEach((p, i) => {
      const pivot = new THREE.Group();
      pivot.position.fromArray(p.pivot_mm);
      pivot.userData.panel = p;
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(...p.size_mm),
        new THREE.MeshStandardMaterial({
          color: i === 0 ? 0x6e8293 : 0xc1a47c,
          roughness: 0.65,
        }),
      );
      mesh.position.fromArray(p.center_mm).sub(pivot.position);
      mesh.add(
        new THREE.LineSegments(
          new THREE.EdgesGeometry(mesh.geometry),
          new THREE.LineBasicMaterial({
            color: 0x514a40,
            transparent: true,
            opacity: 0.6,
          }),
        ),
      );
      pivot.add(mesh);
      group.add(pivot);
    });
    scene.add(group);
    const stateButtons = $("#motion-states");
    stateButtons.classList.toggle("hidden", value.family !== "general_mechanism");
    stateButtons.innerHTML = value.family === "general_mechanism" ? value.spec.states.map((state,index) => {
      const frame = index === 0 ? value.frames[0] : value.frames.find(frame => frame.segment === index - 1 && Math.abs(frame.fraction - 1) < 1e-8);
      return `<button type="button" data-progress="${frame.progress_pct}" aria-pressed="false">${escape(state.name)}</button>`;
    }).join("") : "";
    stateButtons.querySelectorAll("button").forEach(button => button.addEventListener("click", () => {
      playing = false; $("#motion-play").textContent = "▶ Play"; updateAngle(Number(button.dataset.progress));
    }));
    $("#motion-angle").max = value.config.progress_max ?? value.config.max_angle_deg;
    // The native studies already snap to their nearest verified frame. A
    // fractional HTML step can round the final 100% value down by one frame.
    $("#motion-angle").step = value.family === "general_mechanism" || value.family === "panel_hinges" ? "any" : ".1";
    $("#motion-angle").disabled = false;
    $("#motion-play").disabled = false;
    $("#motion-save").disabled = value.family === "general_mechanism";
    $("#motion-state").textContent = value.family === "panel_hinges" || value.family === "general_mechanism"
      ? `${value.frames.length} sampled poses · ${value.passed ? "Geometry checks passed" : "Geometry issues detected"}`
      : `${value.frames.length} sampled poses · ${value.sampled_overlap_free ? "No panel overlap detected" : "Overlap detected in " + value.collision_sample_count + " poses"}`;
    $("#motion-scope").textContent = value.scope;
    drawChart();
    updateAngle(0);
    resizeMotion();
    fitMotion();
    renderCanvas();
  }
  function updateAngle(value) {
    angle = Number(value);
    $("#motion-angle").value = angle;
    $("#motion-angle-label").textContent = num(angle) + "°";
    if (!study || !group) return;
    if (study.family === "general_mechanism") {
      const frame = study.frames.reduce((a,b) => Math.abs(b.progress_pct-angle) < Math.abs(a.progress_pct-angle) ? b : a);
      $("#motion-angle").value = frame.progress_pct;
      $("#motion-angle-label").textContent = num(frame.progress_pct) + "%";
      $("#motion-states").querySelectorAll("button").forEach(button => button.setAttribute("aria-pressed", String(Math.abs(Number(button.dataset.progress) - frame.progress_pct) < 1e-7)));
      const hits = frame.overlaps.flatMap(pair => pair.parts);
      group.children.forEach(mesh => {
        mesh.matrix.set(...frame.pose_matrices[mesh.userData.part.id].flat());
        mesh.matrixWorldNeedsUpdate = true;
        mesh.material.color.set(hits.includes(mesh.userData.part.id) ? 0xc06450 : mesh.userData.baseColor);
      });
      $("#motion-metrics").textContent = `Path ${num(frame.progress_pct)}% · ${frame.extent_mm.map(v=>num(v)).join(" × ")} mm · ${frame.overlaps.length ? "Solid interference" : "No sampled native solid overlap"} · loop error ${frame.loop_position_error_mm.toExponential(1)} mm · hardware and locks unverified`;
      return;
    }
    if (study.family==="panel_hinges") {
      const frame=study.frames.reduce((a,b)=>Math.abs(b.angle_deg-angle)<Math.abs(a.angle_deg-angle)?b:a);
      $("#motion-angle").value=frame.angle_deg;
      $("#motion-angle-label").textContent=num(frame.angle_deg)+"°";
      group.children.forEach(mesh=>{
        const part=mesh.userData.part;
        mesh.matrix.set(...frame.pose_matrices[part.face].flat());
        mesh.matrixWorldNeedsUpdate=true;
        mesh.material.color.set(frame.overlaps.flat().includes(part.id)?0xc06450:mesh.userData.baseColor);
      });
      $("#motion-metrics").textContent=`Checked pose ${num(frame.angle_deg)}° · ${frame.extent_mm.map(v=>num(v)).join(" × ")} mm · ${frame.overlaps.length ? "Solid interference: "+frame.overlaps.map(p=>p.join(" / ")).join(", ") : "No native solid overlap"} · hinge closure ${frame.axis_closure_error_mm.toExponential(1)} mm`;
      return;
    }
    group.children.forEach((pivot) => {
      const p = pivot.userData.panel;
      pivot.rotation[p.axis] = THREE.MathUtils.degToRad(angle * p.direction);
    });
    const frame = study.frames.reduce((a, b) =>
      Math.abs(b.angle_deg - angle) < Math.abs(a.angle_deg - angle) ? b : a,
    );
    $("#motion-metrics").textContent =
      `Nearest sampled envelope (${num(frame.angle_deg)}°): ${frame.extent_mm.map((x) => num(x)).join(" × ")} mm · ${frame.overlaps.length ? "Panel overlap: " + frame.overlaps.map((p) => p.join(" / ")).join(", ") : "No positive-volume panel overlap"}`;
    group.children.forEach((pivot) => {
      const hit = frame.overlaps.flat().includes(pivot.userData.panel.id);
      pivot.children[0].material.color.set(
        hit
          ? 0xc06450
          : pivot.userData.panel.id === "base"
            ? 0x6e8293
            : 0xc1a47c,
      );
    });
  }
  function drawChart() {
    const max = Math.max(...study.frames.flatMap((f) => f.extent_mm));
    const colors = ["#617e99", "#ac8456", "#769176"];
    $("#motion-chart").innerHTML = colors
      .map(
        (color, axis) =>
          `<polyline fill="none" stroke="${color}" stroke-width="2" points="${study.frames.map((f) => `${20 + ((f.progress_pct ?? f.angle_deg) / (study.config.progress_max ?? study.config.max_angle_deg)) * 560},${82 - (f.extent_mm[axis] / max) * 65}`).join(" ")}"/><text x="${20 + axis * 180}" y="103" fill="${color}" font-size="10">${["X width", "Y depth", "Z height"][axis]} · max ${num(Math.max(...study.frames.map((f) => f.extent_mm[axis])))} mm</text>`,
      )
      .join("");
  }
  $("#motion-run").onclick = () =>
    runTask(async () => {
      const base = context();
      $("#motion-state").textContent = "Checking native mechanism geometry…";
      const value = await bridge.api("/motion", {
        document: bridge.getState().document,
        config: snapshot.document.metadata?.design_mechanism ? {family: "general_mechanism", samples_per_segment: Number($("#motion-samples").value)} : {
          family: snapshot.folding ? "panel_hinges" : "enclosure_walls",
          max_angle_deg: Number($("#motion-max").value),
          samples: Number($("#motion-samples").value),
        },
      }, Number($("#motion-samples").value)>73 ? 600000 : 180000);
      if (base !== context())
        throw new Error("Geometry changed during simulation. Run again.");
      studyKey = motionSignature(snapshot);
      displayStudy(value);
    });
  [$("#motion-max"), $("#motion-samples")].forEach((input) =>
    input.addEventListener("change", () => {
      playing = false;
      $("#motion-save").disabled = true;
      $("#motion-play").textContent = "▶ Play";
      $("#motion-state").textContent =
        "Motion settings changed. Run the study again to update results.";
    }),
  );
  $("#motion-angle").oninput = (event) => {
    playing = false;
    $("#motion-play").textContent = "▶ Play";
    updateAngle(event.target.value);
  };
  $("#motion-play").onclick = () => {
    playing = !playing;
    $("#motion-play").textContent = playing ? "Ⅱ Pause" : "▶ Play";
    lastTime = performance.now();
  };
  $("#motion-reset").onclick = () => {
    playing = false;
    $("#motion-play").textContent = "▶ Play";
    updateAngle(0);
  };
  $("#motion-fit").onclick = fitMotion;
  $("#motion-focus").onclick = () => {
    const focused = document.body.classList.toggle("motion-focus");
    $("#motion-focus").textContent = focused ? "Back to editors" : "Focus view";
    resizeMotion();
    fitMotion();
  };

  $("#motion-save").onclick = () =>
    runTask(async () => {
      if (
        !study ||
        studyKey !== motionSignature(snapshot) ||
        !motionSettingsMatch()
      )
        throw new Error("Run the study again for this geometry.");
      const doc = copy(bridge.getState().document);
      doc.metadata.motion = study.config;
      await bridge.save(doc, "Attach wall motion study");
      bridge.toast(
        "Study settings saved; the export bundle includes its report.",
      );
    });

  function motionSettingsMatch() {
    return (
      study &&
      study.config.max_angle_deg === Number($("#motion-max").value) &&
      study.config.samples === Number($("#motion-samples").value)
    );
  }

  function renderCanvas() {
    if (!snapshot) return;
    const d = bridge.getState().document,
      meta = d.metadata || {},
      r = snapshot.requirements_state;
    const checks = r?.checks || [];
    const failed = checks.filter((c) => c.status === "fail").length;
    const modelImage = bridge.modelImage?.();
    const fold=snapshot.folding, p=fold?.spec;
    const foldFeature=d.features.find(f=>f.type==="folding_assembly"&&!f.suppressed);
    const enclosure=Boolean(meta.source_spec&&meta.source_requirements);
    const stages = [
      {
        title: "Brief",
        tag: "01 · INTENT",
        tab: "project",
        content: `<p>${escape(meta.brief || "Add your design brief and fabrication context.")}</p>`,
        action: "Edit brief",
      },
      {
        title: fold ? "Folding parameters" : enclosure ? "Requirements" : "Design definition",
        tag: enclosure ? "02 · CONTRACT" : "02 · DEFINITION",
        tab: enclosure ? "project" : "model",
        feature: foldFeature?.id,
        content: fold ? `<span class="canvas-badge">${escape(fold.family.replaceAll("_"," "))} · ${fold.panel_count} panels</span><p>Nominal pitch ${num(p.panel_width)}${p.family==="cube_net" ? "" : " × "+num(p.panel_height)} mm<br>Panel thickness ${num(p.thickness)} mm</p><p>Pin Ø ${num(p.pin_diameter)} · bore Ø ${num(p.pin_diameter+2*p.radial_clearance)} mm<br>Radial gap ${num(p.radial_clearance,2)} · end gap ${num(p.axial_clearance,2)} mm</p>` : enclosure ? `<span class="canvas-badge ${r?.status === "stale" || failed ? "warning" : ""}">${escape(r?.status || "unbound")}${failed ? " · " + failed + " failing" : ""}</span><p>${escape(meta.source_spec.material.replaceAll("_", " "))} · ${num(meta.source_spec.thickness_mm)} mm panels</p><p>Capacity ≥ ${num(meta.source_requirements.min_capacity_l, 2)} L<br>Mass ≤ ${num(meta.source_requirements.max_mass_kg, 2)} kg</p>` : `<p>${d.features.length} editable features · ${snapshot.metrics?.solid_count || 0} solids.</p><p>Inspect source dimensions in the feature editor. Geometry validity is checked independently; review the brief's functional requirements separately.</p>`,
        action: enclosure ? "Edit requirements" : "Edit parameters",
      },
      {
        title: enclosure ? "Design options" : fold ? "Refine folding" : "Refine geometry",
        tag: enclosure ? "03 · EXPLORE" : "03 · REFINE",
        tab: enclosure ? "project" : "model",
        feature: foldFeature?.id,
        content: enclosure ? `<p>Compare feasible stock sizes against the same requirements.</p><p>Lock clear dimensions or allow resizing within the envelope.</p>` : fold ? `<p>Edit panel thickness, hinge clearances, setback and driver angle in the feature inspector, or request a reviewed Meta revision.</p><p>Rerun Motion after geometry edits. Use the print pack for separated components and a fit coupon.</p>` : `<p>Edit native features, add supported operations to an imported solid, or request a reviewed Meta revision.</p><p>Save revisions to preserve your design history.</p>`,
        action: enclosure ? "Compare designs" : "Open feature editor",
      },
      {
        title: "Editable CAD",
        tag: "04 · GEOMETRY",
        tab: "model",
        content: `${modelImage ? `<img class="canvas-model-image" src="${modelImage}" alt="Current CAD geometry">` : ""}<p>${d.features.length} features · ${snapshot.metrics?.solid_count || 0} solids</p>`,
        action: "Open model",
      },
      {
        title: meta.design_mechanism ? "Mechanism motion" : snapshot.folding ? "Folding motion" : "Wall motion",
        tag: "05 · SIMULATION",
        tab: "motion",
        content: `<span class="canvas-badge">${study && studyKey === motionSignature(snapshot) ? "Current session study" : "Run study"}</span><p>${study && studyKey === motionSignature(snapshot) ? `${study.frames.length} sampled poses<br>${study.sampled_overlap_free ? "No sampled solid overlap" : "Overlap detected"}` : meta.design_mechanism ? "Native solids with declared sliding or rotating joints." : snapshot.folding ? "Rigid panels, real hinge barrels and removable pins." : "Finite-thickness enclosure walls with explicit virtual hinges."}</p><p>Loads and physical fit require separate validation.</p>`,
        action: "Open simulation",
      },
      {
        title: "Drawings & export",
        tag: "06 · DELIVER",
        tab: "drawing",
        content: `<img class="canvas-drawing-image" src="data:image/svg+xml;charset=utf-8,${encodeURIComponent(snapshot.drawing_svg)}" alt="Drawing of this revision"><p>STEP · STL · DXF · PDF · editable JSON</p>`,
        action: "Open drawing",
      },
    ];
    $("#workflow-cards").innerHTML = stages
      .map(
        (s, i) =>
          `<article class="workflow-stage-card" style="left:${70 + i * 500}px;top:${i % 2 ? 240 : 110}px" data-canvas-stage="${s.tab}"><small>${s.tag}</small><h2>${s.title}</h2><div class="workflow-card-content">${s.content}</div><button data-tab="${s.tab}"${s.feature ? ` data-feature="${escape(s.feature)}"` : ""}>${s.action} ↗</button></article>`,
      )
      .join("");
    $("#canvas-map-cards").innerHTML = stages
      .map(
        (s, i) =>
          `<span style="left:${((70 + i * 500) / boardWidth) * 100}%;top:${((i % 2 ? 240 : 110) / boardHeight) * 100}%;width:${(420 / boardWidth) * 100}%;height:${(350 / boardHeight) * 100}%"></span>`,
      )
      .join("");
    $("#canvas-revision").textContent = (snapshot.id || "Preview").slice(-12);
    $("#canvas-pip-image").src = modelImage || "";
    $(".canvas-pip").classList.toggle("hidden", !modelImage);
    updateMinimap();
  }
  function updateMinimap() {
    const host = $("#workflow-board"),
      view = $("#canvas-map-view");
    view.style.left = (host.scrollLeft / (boardWidth * zoom)) * 100 + "%";
    view.style.top = (host.scrollTop / (boardHeight * zoom)) * 100 + "%";
    view.style.width =
      Math.min(100, (host.clientWidth / (boardWidth * zoom)) * 100) + "%";
    view.style.height =
      Math.min(100, (host.clientHeight / (boardHeight * zoom)) * 100) + "%";
  }
  function setZoom(value, point) {
    const host = $("#workflow-board"),
      old = zoom;
    zoom = Math.min(1.6, Math.max(0.12, value));
    const x = point?.x ?? host.clientWidth / 2,
      y = point?.y ?? host.clientHeight / 2;
    $("#workflow-world").style.transform = `scale(${zoom})`;
    $("#workflow-world-size").style.width = boardWidth * zoom + "px";
    $("#workflow-world-size").style.height = boardHeight * zoom + "px";
    host.scrollLeft = ((host.scrollLeft + x) / old) * zoom - x;
    host.scrollTop = ((host.scrollTop + y) / old) * zoom - y;
    $("#canvas-zoom").textContent = Math.round(zoom * 100) + "%";
    updateMinimap();
  }
  function fitCanvas() {
    const host = $("#workflow-board");
    setZoom(
      Math.min(
        (host.clientWidth - 30) / boardWidth,
        (host.clientHeight - 20) / boardHeight,
      ),
    );
    host.scrollTo(0, 0);
    updateMinimap();
  }
  const board = $("#workflow-board");
  board.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      if (e.shiftKey) {
        board.scrollLeft += e.deltaY + e.deltaX;
        return;
      }
      const rect = board.getBoundingClientRect();
      setZoom(zoom * Math.exp(-e.deltaY * 0.0015), {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top,
      });
    },
    { passive: false },
  );
  board.addEventListener("pointerdown", (e) => {
    if (e.target.closest("button,input,textarea,article")) return;
    if (e.button !== 0 && e.button !== 1) return;
    pan = {
      x: e.clientX,
      y: e.clientY,
      left: board.scrollLeft,
      top: board.scrollTop,
    };
    board.setPointerCapture(e.pointerId);
    board.classList.add("panning");
  });
  board.addEventListener("pointermove", (e) => {
    if (!pan) return;
    board.scrollLeft = pan.left - e.clientX + pan.x;
    board.scrollTop = pan.top - e.clientY + pan.y;
  });
  board.addEventListener("pointerup", () => {
    pan = null;
    board.classList.remove("panning");
  });
  board.addEventListener("pointercancel", () => {
    pan = null;
    board.classList.remove("panning");
  });
  board.addEventListener("scroll", updateMinimap);
  board.addEventListener("dblclick", (e) => {
    const card = e.target.closest("[data-canvas-stage]");
    if (card) bridge.setTab(card.dataset.canvasStage);
  });
  board.addEventListener("keydown", (e) => {
    if (e.key === "+" || e.key === "=") setZoom(zoom * 1.2);
    if (e.key === "-") setZoom(zoom / 1.2);
    if (e.key === "Home") {
      e.preventDefault();
      fitCanvas();
    }
  });
  $("#canvas-plus").onclick = () => setZoom(zoom * 1.2);
  $("#canvas-minus").onclick = () => setZoom(zoom / 1.2);
  $("#canvas-fit").onclick = fitCanvas;
  $("#canvas-map").onclick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    board.scrollLeft =
      ((e.clientX - rect.left) / rect.width) * boardWidth * zoom -
      board.clientWidth / 2;
    board.scrollTop =
      ((e.clientY - rect.top) / rect.height) * boardHeight * zoom -
      board.clientHeight / 2;
  };
  new ResizeObserver(updateMinimap).observe(board);
  setZoom(zoom);

  return {
    update(value) {
      snapshot = value;
      const general = value.document.metadata?.design_mechanism;
      $("#motion-samples").parentElement.firstChild.textContent = general ? "Samples per transition " : "Sample poses ";
      $("#motion-tab h1").textContent=general ? "Mechanism motion" : value.folding ? value.folding.family.replaceAll("_"," ").replace(/^./,c=>c.toUpperCase())+" folding" : "Wall folding";
      $("#motion-max").disabled = !!general;
      $("#motion-max").parentElement.classList.toggle("hidden", !!general);
      $("#motion-save").classList.toggle("hidden", !!general);
      const samplesControl=$("#motion-samples");
      for (const count of [181,361,721]) {
        let option=Array.from(samplesControl.options).find(o=>o.value===String(count));
        if (!option) { option=document.createElement("option");option.value=count;option.textContent=String(count);samplesControl.append(option); }
        option.disabled=option.hidden=!value.folding;
      }
      if (!value.folding && Number(samplesControl.value)>73) samplesControl.value=37;
      $("#motion-chart").setAttribute("aria-label","Outside envelope through sampled motion");
      if (!study) $("#motion-metrics").textContent="Simulation is bound to the current CAD revision.";
      $("#motion-angle").parentElement.firstChild.textContent=general ? "Path progress " : value.folding ? "Driver angle " : "Wall angle ";
      if (!study && general) {
        $("#motion-angle-label").textContent = "0%";
        const count = String(general.samples_per_segment);
        if (!Array.from(samplesControl.options).some(o => o.value === count)) {
          const option = document.createElement("option"); option.value = count; option.textContent = count; samplesControl.append(option);
        }
        samplesControl.value = count;
        $("#motion-max").value = 90;
      }
      $("#motion-max").max=value.folding?.absolute_limit_deg || 90;
      if (!study && !value.document.metadata?.motion && value.folding) {
        $("#motion-max").value=value.folding.default_limit_deg;
        $("#motion-samples").value=73;
      }
      if (!study && !general && value.document.metadata?.motion) {
        $("#motion-max").value = value.document.metadata.motion.max_angle_deg;
        $("#motion-samples").value = value.document.metadata.motion.samples;
      }
      if (revision !== value.id) {
        if (!dirty) loadForm();
        else if (revision)
          message(
            "Revision changed. Your form draft is retained; reload saved values before applying to the new revision.",
            true,
          );
        revision = value.id;
        optionsContext = null;
        $("#project-options").classList.add("hidden");
      }
      const binding = value.requirements_state?.status || "unbound";
      if (!study) {
        $("#motion-state").textContent = general ? "Ready to check declared motion on native solids. Hardware and locks need separate verification." : value.folding ? "Ready to check real panels, pins and hinge alignment." :
          binding === "current"
            ? value.document.metadata.source_spec.lid
              ? "Remove the top panel in Project before running wall motion."
              : "Ready to run wall motion for this revision."
            : "Build an open enclosure in Project to begin.";
      }
      const fails =
        value.requirements_state?.checks?.filter((c) => c.status === "fail")
          .length || 0;
      $("#project-binding").textContent =
        binding === "unbound"
          ? "No enclosure contract attached. These settings define a new enclosure."
          : binding === "stale"
            ? "Custom geometry differs from the retained enclosure. Rebuilding replaces it in a new revision."
            : `Requirements: current${fails ? " · " + fails + " failing" : ""} · Changes create a new CAD revision with updated drawings.`;
      $("#project-replace-label").classList.toggle(
        "hidden",
        binding === "current" || !value.document.features.length,
      );
      if (studyKey && studyKey !== motionSignature(value)) {
        $("#motion-states").classList.add("hidden");
        $("#motion-states").innerHTML = "";
        study = null;
        playing = false;
        clearGroup();
        $("#motion-state").textContent =
          "Geometry changed. Run the motion study for this revision.";
        $("#motion-play").disabled = true;
        $("#motion-angle").disabled = true;
        $("#motion-save").disabled = true;
        $("#motion-chart").innerHTML = "";
        $("#motion-metrics").textContent = "Previous motion results are stale.";
      }
      renderCanvas();
    },
    tabChanged(tab) {
      if (tab !== "motion") {
        document.body.classList.remove("motion-focus");
        $("#motion-focus").textContent = "Focus view";
      }
      document.body.classList.toggle("canvas-focus", tab === "canvas");
      if (tab !== "motion") {
        playing = false;
        $("#motion-play").textContent = "▶ Play";
      }
      if (tab === "motion") {
        try {
          initMotion();
          resizeMotion();
        } catch (error) {
          $("#motion-state").textContent =
            "3D preview unavailable: " + error.message;
        }
      }
      if (tab === "canvas") {
        renderCanvas();
        setZoom(zoom);
      }
    },
    fitCanvas,
  };
}
