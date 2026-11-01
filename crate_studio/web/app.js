const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const num = (v, digits = 1) =>
  Number.isFinite(Number(v))
    ? Number(v).toLocaleString(undefined, { maximumFractionDigits: digits })
    : "—";
const readable = (s) =>
  String(s)
    .replace(/_/g, " ")
    .replace(/\bmm\b/g, "mm");
const formatCheckValue = (value) =>
  Array.isArray(value)
    ? value
        .map((v) => (typeof v === "number" ? num(v, 3) : String(v)))
        .join(" · ")
    : typeof value === "number"
      ? num(value, 3)
      : String(value);
const state = {
  saved: null,
  project: null,
  materials: [],
  projects: [],
  preview: false,
  selected: null,
  job: null,
  requirements: {},
  model: {},
  busy: false,
};
let three,
  scene,
  camera,
  renderer,
  controls,
  assembly,
  dimensions,
  grid,
  raycaster,
  pointer;
let meshes = [],
  resizeObserver,
  toastTimer;

async function api(path, data, method, timeoutMs = 30000) {
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(path, {
      method: method || (data === undefined ? "GET" : "POST"),
      headers: data === undefined ? {} : { "Content-Type": "application/json" },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal: controller.signal,
    });
    const type = res.headers.get("content-type") || "";
    const body = type.includes("json") ? await res.json() : await res.text();
    if (!res.ok)
      throw new Error(
        typeof body === "string"
          ? body
          : body.error?.message ||
            body.error ||
            body.detail ||
            `Request failed (${res.status})`,
      );
    return body;
  } catch (e) {
    if (e.name === "AbortError")
      throw new Error(
        "The server response timed out. Check the connection and try again.",
      );
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
function toast(message, error = false) {
  $("#toast").textContent = message;
  $("#toast").classList.toggle("error", error);
  $("#toast").classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.add("hidden"), 5500);
}
function status(message) {
  $("#status-text").textContent = message;
}
function material() {
  return (
    state.materials.find((x) => x.id === state.project?.spec.material) || {
      name: readable(state.project?.spec.material || "Material"),
      color: "#c8b28b",
    }
  );
}
function validSnapshot(value) {
  if (!value || !value.spec || !Array.isArray(value.panels))
    throw new Error("The design engine returned an incomplete project.");
  return value;
}
function useProject(value, preview = false) {
  state.project = validSnapshot(value.project || value);
  state.preview = preview;
  state.previewJob = null;
  if (!preview) state.saved = state.project;
  state.requirements = { ...(state.project.requirements || {}) };
  state.selected = null;
  renderAll();
  if (!preview) {
    $("#model-provenance").textContent =
      state.project.source === "meta"
        ? `${state.project.provenance?.model || state.model.name || "Meta"} · Applied revision`
        : `${state.project.source === "import" ? "Imported" : "Manual"} design${state.model.configured ? " · Meta connected" : ""}`;
    if (state.project.source !== "meta" && !state.busy)
      $("#agent-result").classList.add("hidden");
  }
}
function renderAll() {
  const p = state.project,
    s = p.spec,
    m = p.metrics || {};
  $("#project-name").textContent = s.name || "Panel crate";
  $("#model-title").textContent = s.name || "Panel crate";
  $("#version-label").textContent = state.preview
    ? "Unsaved preview · save to create a version"
    : `${p.label || "Saved design"}${p.id ? " · " + String(p.id).slice(0, 8) : ""}`;
  $("#version-label").classList.toggle("preview-badge", state.preview);
  $("#model-subtitle").textContent =
    `${num(m.outer_width_mm)} × ${num(m.outer_depth_mm)} × ${num(m.outer_height_mm)} mm · ${material().name}`;
  $("#name-input").value = s.name || "Panel crate";
  $("#width").value = s.inner_width_mm;
  $("#depth").value = s.inner_depth_mm;
  $("#height").value = s.inner_height_mm;
  $("#thickness").value = s.thickness_mm;
  $("#material").value = s.material;
  $("#lid").checked = !!s.lid;
  $("#part-count").textContent = p.panels.length;
  $("#part-tree").innerHTML = p.panels
    .map(
      (x) =>
        `<button class="part-item" data-part="${esc(x.id)}">${esc(x.name)}<small>01</small></button>`,
    )
    .join("");
  $("#discard-preview").classList.toggle("hidden", !state.preview);
  $("#save-project").textContent = state.preview
    ? "Save preview"
    : "Save version";
  $("#geometry-status").textContent =
    `${p.panels.length} panels · ${state.preview ? "Preview" : "Saved geometry"}`;
  $("#summary").innerHTML = [
    [
      "Outer envelope",
      `${num(m.outer_width_mm)} × ${num(m.outer_depth_mm)} × ${num(m.outer_height_mm)}`,
    ],
    ["Usable capacity", `${num(m.capacity_l, 2)} L`],
    ["Estimated mass", `${num(m.mass_kg, 2)} kg`],
    ["Panel count", p.panels.length],
    ["Sheet thickness", `${num(s.thickness_mm)} mm`],
    [
      "Floor screening",
      p.requirements.payload_kg > 0
        ? `${num(m.floor_deflection_mm, 3)} mm`
        : "Not requested",
    ],
  ]
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
    .join("");
  renderRequirements();
  renderChecks();
  renderCutlist();
  renderDrawing();
  renderHistory();
  renderGeometry();
  selectPart(null);
  status(
    state.preview
      ? "Preview ready · save to retain this revision"
      : "Design engine connected · project saved locally",
  );
}
function renderRequirements() {
  const r = state.requirements;
  const items = [];
  items.push(
    r.lock_inner_dimensions
      ? "Preserve internal clearance"
      : "Resizing permitted within envelope",
  );
  if (r.min_capacity_l != null)
    items.push(`Capacity ≥ ${num(r.min_capacity_l)} L`);
  if (r.max_mass_kg != null) items.push(`Mass ≤ ${num(r.max_mass_kg)} kg`);
  if (r.max_outer_width_mm != null)
    items.push(
      `Outer envelope ≤ ${num(r.max_outer_width_mm)} × ${num(r.max_outer_depth_mm)} × ${num(r.max_outer_height_mm)} mm`,
    );
  if (r.payload_kg > 0)
    items.push(
      `Floor screening: ${num(r.payload_kg)} kg / ≤ ${num(r.max_floor_deflection_mm)} mm`,
    );
  if (r.objective) items.push(readable(r.objective));
  $("#requirements").innerHTML = items.length
    ? items.map((x) => `<div class="requirement">${esc(x)}</div>`).join("")
    : "<p>No constraints specified.</p>";
}
function checkSymbol(c) {
  return c.status === "pass" ? "✓" : c.status === "fail" ? "×" : "i";
}
function renderChecks() {
  const p = state.project,
    checks = p.checks || [];
  const failed = checks.filter((c) => c.status === "fail").length,
    passed = checks.filter((c) => c.status === "pass").length;
  $("#check-count").textContent = `${passed}/${checks.length}`;
  $("#check-dot").style.background = failed ? "#c47a6a" : "#70a494";
  const sum = $("#verification-summary");
  sum.textContent = failed
    ? `${failed} check${failed === 1 ? "" : "s"} failed`
    : `${passed} checks passed`;
  sum.className = "status-pill" + (failed ? " fail" : "");
  $("#verification-mini").innerHTML = checks
    .slice(0, 3)
    .map(
      (c) =>
        `<div class="check-mini"><span class="check-symbol ${c.status === "fail" ? "fail" : c.status === "info" ? "warn" : ""}">${checkSymbol(c)}</span><span>${esc(c.label || readable(c.id))}</span></div>`,
    )
    .join("");
  $("#verification-content").innerHTML =
    checks
      .map(
        (c) =>
          `<div class="check-card"><span class="check-symbol ${c.status === "fail" ? "fail" : c.status === "info" ? "warn" : ""}">${checkSymbol(c)}</span><div><strong>${esc(c.label || readable(c.id))}</strong><p>${esc(c.detail || "")}${c.actual !== undefined ? `<br>Actual: ${esc(formatCheckValue(c.actual))} ${esc(c.unit || "")}` : ""}${c.limit !== undefined ? ` · Limit: ${esc(formatCheckValue(c.limit))} ${esc(c.unit || "")}` : ""}</p></div></div>`,
      )
      .join("") +
    (p.notes || [])
      .map(
        (n) =>
          `<div class="check-card"><span class="check-symbol warn">i</span><div><strong>Engineering note</strong><p>${esc(n)}</p></div></div>`,
      )
      .join("");
}
function renderCutlist() {
  const p = state.project;
  const rows =
    p.cut_list ||
    p.panels.map((x) => {
      const flat = ["base", "lid"].includes(x.id);
      return {
        part: x.id,
        quantity: 1,
        width_mm: flat
          ? x.size_mm[0]
          : ["front", "back"].includes(x.id)
            ? x.size_mm[0]
            : x.size_mm[1],
        height_mm: flat ? x.size_mm[1] : x.size_mm[2],
        thickness_mm: p.spec.thickness_mm,
      };
    });
  $("#cutlist-content").innerHTML =
    `<table class="data-table"><thead><tr><th>PART</th><th>QTY</th><th>WIDTH / MM</th><th>HEIGHT / MM</th><th>THICKNESS / MM</th><th>MATERIAL</th></tr></thead><tbody>${rows.map((x) => `<tr><td>${esc(p.panels.find((y) => y.id === x.part)?.name || x.part)}</td><td class="numeric">${num(x.quantity, 0)}</td>${[x.width_mm, x.height_mm, x.thickness_mm].map((v) => `<td class="numeric">${num(v, 2)}</td>`).join("")}<td>${esc(material().name)}</td></tr>`).join("")}</tbody></table><p class="section-description">Panel sizes are finished dimensions. Allow for cutting kerf, joints, fastening, tolerances and material-specific fabrication practices.</p>`;
}
function renderHistory() {
  const list = state.projects;
  $("#history").innerHTML = list.length
    ? list
        .map(
          (p) =>
            `<button class="history-item ${p.id === state.saved?.id ? "active" : ""}" data-project="${esc(p.id)}"><span class="history-node"></span><span><strong>${esc(p.label || p.spec?.name || p.name || "Saved version")}</strong><small>${esc(p.created_at ? new Date(p.created_at).toLocaleString(undefined, { timeZone: "Asia/Kolkata", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZoneName: "short" }) : String(p.id).slice(0, 8))}${p.source ? " · " + esc(p.source) : ""}</small></span></button>`,
        )
        .join("")
    : '<p class="empty-note">No saved versions yet.</p>';
}
async function refreshHistory() {
  const result = await api("/api/projects");
  state.projects = Array.isArray(result) ? result : result.projects || [];
  renderHistory();
}
function formSpec() {
  return {
    ...state.project.spec,
    name: $("#name-input").value.trim() || "Panel crate",
    inner_width_mm: Number($("#width").value),
    inner_depth_mm: Number($("#depth").value),
    inner_height_mm: Number($("#height").value),
    thickness_mm: Number($("#thickness").value),
    material: $("#material").value,
    lid: $("#lid").checked,
  };
}
function sameRecord(a, b) {
  if (!a || !b) return a === b;
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])];
  return keys.every((k) => a[k] === b[k]);
}
function inspectorDirty() {
  return !!state.project && !sameRecord(formSpec(), state.project.spec);
}
function proposalCanApply() {
  const c = state.proposalContext;
  if (!c || state.saved?.id !== c.base.id || inspectorDirty()) return false;
  if (state.preview)
    return (
      state.previewJob === c.jobId &&
      sameRecord(state.project.spec, state.proposal?.result?.spec) &&
      sameRecord(state.requirements, state.proposal?.result?.requirements)
    );
  return (
    sameRecord(formSpec(), c.base.spec) &&
    sameRecord(state.requirements, c.base.requirements)
  );
}
function guardProposal() {
  if (proposalCanApply()) return true;
  toast(
    "This proposal belongs to an earlier design. Restore its original version or request a new proposal.",
    true,
  );
  return false;
}
async function preview() {
  const btn = $("#update-design");
  btn.disabled = true;
  try {
    const result = await api("/api/design", {
      spec: formSpec(),
      requirements: state.requirements,
    });
    useProject(result, true);
    toast("Preview updated. Save this version when ready.");
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
}
async function saveProject() {
  if (!state.project || !$("#design-form").reportValidity()) return;
  if (state.previewJob && proposalCanApply()) {
    await applyProposal();
    return;
  }
  const btn = $("#save-project");
  btn.disabled = true;
  try {
    const p = await api("/api/projects", {
      spec: formSpec(),
      requirements: state.requirements,
      parent_id: state.saved?.id,
      label: state.preview ? "Manual revision" : "Saved version",
      source: "manual",
    });
    useProject(p);
    await refreshHistory();
    toast("Version saved locally.");
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false;
  }
}
function setTab(tab) {
  $$("[data-tab]").forEach((x) =>
    x.classList.toggle("active", x.dataset.tab === tab),
  );
  $$(".view").forEach((x) =>
    x.classList.toggle("active", x.id === tab + "-view"),
  );
  if (tab === "model") resize();
}
function selectPart(id) {
  state.selected = id;
  $$("[data-part]").forEach((b) =>
    b.classList.toggle("active", b.dataset.part === id),
  );
  const part = state.project?.panels.find((p) => p.id === id);
  $("#selected-label").textContent = part?.name || "All panels";
  $("#selection-status").textContent = part
    ? `${part.name} · ${part.size_mm.map((v) => num(v)).join(" × ")} mm`
    : "No selection";
  meshes.forEach((m) => {
    m.material.color.set(m.userData.id === id ? "#8fa5e8" : m.userData.color);
    m.material.emissive.set(m.userData.id === id ? "#152349" : "#000000");
  });
}

async function setup3D() {
  try {
    three = await import("/assets/vendor/three.module.js");
    const { OrbitControls } = await import("/assets/vendor/OrbitControls.js");
    scene = new three.Scene();
    camera = new three.PerspectiveCamera(35, 1, 0.1, 100000);
    renderer = new three.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = three.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = three.PCFSoftShadowMap;
    $("#viewport").append(renderer.domElement);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.09;
    controls.minDistance = 20;
    controls.maxDistance = 25000;
    controls.maxPolarAngle = Math.PI * 0.93;
    scene.add(new three.HemisphereLight(0xffffff, 0x929dac, 2.2));
    const light = new three.DirectionalLight(0xffffff, 3);
    light.position.set(500, 1100, 700);
    scene.add(light);
    const fill = new three.DirectionalLight(0xc8d6f5, 1.2);
    fill.position.set(-700, 500, -300);
    scene.add(fill);
    assembly = new three.Group();
    scene.add(assembly);
    dimensions = new three.Group();
    scene.add(dimensions);
    raycaster = new three.Raycaster();
    pointer = new three.Vector2();
    let down;
    renderer.domElement.addEventListener(
      "pointerdown",
      (e) => (down = [e.clientX, e.clientY]),
    );
    renderer.domElement.addEventListener("pointerup", (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5)
        return;
      const box = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((e.clientX - box.left) / box.width) * 2 - 1,
        (-(e.clientY - box.top) / box.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      selectPart(
        raycaster.intersectObjects(meshes)[0]?.object.userData.id || null,
      );
    });
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe($("#viewport"));
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });
    resize();
    return true;
  } catch (e) {
    console.warn("WebGL renderer unavailable:", e.message);
    $("#viewport").classList.add("hidden");
    $("#fallback").classList.remove("hidden");
    $("#geometry-status").textContent = "2D fallback · WebGL unavailable";
    return false;
  }
}
function resize() {
  if (!renderer) return;
  const { width, height } = $("#viewport").getBoundingClientRect();
  if (!width || !height) return;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}
function disposeGroup(group) {
  if (!group) return;
  while (group.children.length) {
    const obj = group.children[0];
    obj.traverse((x) => {
      x.geometry?.dispose();
      if (x.material) {
        const ms = Array.isArray(x.material) ? x.material : [x.material];
        ms.forEach((m) => {
          m.map?.dispose();
          m.dispose();
        });
      }
    });
    group.remove(obj);
  }
}
function renderGeometry() {
  const p = state.project;
  if (!p) return;
  if (!renderer) {
    renderFallback();
    return;
  }
  disposeGroup(assembly);
  disposeGroup(dimensions);
  meshes = [];
  const m = p.metrics,
    mat = material();
  let color = mat.color || "#c6b08d";
  const center = [0, 0, m.outer_height_mm / 2];
  for (const part of p.panels) {
    const size = part.size_mm,
      c = part.center_mm,
      data = p.geometry?.parts?.find((x) => x.id === part.id);
    let geo;
    if (data?.vertices?.length && data?.triangles?.length) {
      geo = new three.BufferGeometry();
      const vertices = [];
      for (let i = 0; i < data.vertices.length; i += 3)
        vertices.push(
          data.vertices[i] - c[0],
          data.vertices[i + 2] - c[2],
          -(data.vertices[i + 1] - c[1]),
        );
      geo.setAttribute(
        "position",
        new three.Float32BufferAttribute(vertices, 3),
      );
      geo.setIndex(data.triangles);
      geo.computeVertexNormals();
    } else {
      geo = new three.BoxGeometry(size[0], size[2], size[1]);
    }
    const mesh = new three.Mesh(
      geo,
      new three.MeshStandardMaterial({
        color,
        roughness: 0.72,
        metalness: p.spec.material.includes("steel") ? 0.5 : 0.03,
        wireframe: $("#show-wireframe").checked,
      }),
    );
    mesh.position.set(c[0], c[2], -c[1]);
    mesh.userData = {
      id: part.id,
      color,
      base: mesh.position.clone(),
      direction: new three.Vector3(c[0], c[2] - center[2], -c[1]).normalize(),
    };
    const edges = new three.LineSegments(
      new three.EdgesGeometry(geo),
      new three.LineBasicMaterial({
        color: 0x756e63,
        transparent: true,
        opacity: 0.38,
      }),
    );
    mesh.add(edges);
    assembly.add(mesh);
    meshes.push(mesh);
  }
  if (grid) {
    scene.remove(grid);
    grid.geometry.dispose();
    grid.material.dispose();
  }
  const extent = Math.max(m.outer_width_mm, m.outer_depth_mm) * 4;
  grid = new three.GridHelper(extent, 40, 0xd1d8e2, 0xe2e6ed);
  grid.position.y = -1;
  scene.add(grid);
  addDimensions();
  explode();
  fitView();
}
function fitView(view) {
  if (!camera || !state.project) return;
  const m = state.project.metrics;
  const center = new three.Vector3(0, m.outer_height_mm * 0.48, 0);
  const radius =
    Math.hypot(m.outer_width_mm, m.outer_depth_mm, m.outer_height_mm) / 2;
  const vertical = three.MathUtils.degToRad(camera.fov),
    horizontal = 2 * Math.atan(Math.tan(vertical / 2) * camera.aspect);
  const margin = window.innerWidth < 1050 ? 1.28 : 1.14;
  const dist = (radius / Math.sin(Math.min(vertical, horizontal) / 2)) * margin;
  const choice =
    view ||
    $$("[data-view]").find((x) => x.classList.contains("active"))?.dataset
      .view ||
    "iso";
  const dir = {
    iso: [1.2, 0.95, 1.3],
    front: [0, 0.01, 1],
    top: [0, 1, 0.001],
    right: [1, 0.01, 0],
  }[choice];
  camera.position
    .copy(center)
    .add(new three.Vector3(...dir).normalize().multiplyScalar(dist));
  camera.up.set(0, 1, 0);
  controls.target.copy(center);
  controls.update();
  $$("[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === choice),
  );
}
function explode() {
  const amount = Number($("#explode").value) / 100;
  $("#explode-value").textContent = `${Math.round(amount * 100)}%`;
  const max = state.project
    ? Math.max(
        state.project.metrics.outer_width_mm,
        state.project.metrics.outer_depth_mm,
      )
    : 500;
  meshes.forEach((m) =>
    m.position
      .copy(m.userData.base)
      .addScaledVector(m.userData.direction, amount * max * 0.25),
  );
  if (dimensions)
    dimensions.visible = $("#show-dimensions").checked && amount === 0;
}
function addDimensions() {
  if (!three || !state.project) return;
  const m = state.project.metrics,
    w = m.outer_width_mm,
    d = m.outer_depth_mm,
    h = m.outer_height_mm,
    off = Math.max(w, d) * 0.1;
  const line = (pts) => {
    const geo = new three.BufferGeometry().setFromPoints(
      pts.map((p) => new three.Vector3(...p)),
    );
    dimensions.add(
      new three.Line(
        geo,
        new three.LineBasicMaterial({
          color: 0x8d9db4,
          transparent: true,
          opacity: 0.75,
        }),
      ),
    );
  };
  const label = (text, pos) => {
    const canvas = document.createElement("canvas");
    canvas.width = 384;
    canvas.height = 80;
    const ctx = canvas.getContext("2d");
    ctx.font = "40px Consolas, monospace";
    ctx.textAlign = "center";
    ctx.fillStyle = "#53647d";
    ctx.fillText(text, 192, 53);
    const sprite = new three.Sprite(
      new three.SpriteMaterial({
        map: new three.CanvasTexture(canvas),
        transparent: true,
        depthTest: false,
      }),
    );
    sprite.position.set(...pos);
    sprite.scale.set(w * 0.27, w * 0.056, 1);
    dimensions.add(sprite);
  };
  line([
    [-w / 2, 0, d / 2],
    [-w / 2, 0, d / 2 + off],
    [w / 2, 0, d / 2 + off],
    [w / 2, 0, d / 2],
  ]);
  label(`${num(w)} mm`, [0, 0, d / 2 + off * 1.6]);
  line([
    [w / 2, 0, d / 2],
    [w / 2 + off, 0, d / 2],
    [w / 2 + off, 0, -d / 2],
    [w / 2, 0, -d / 2],
  ]);
  label(`${num(d)} mm`, [w / 2 + off * 1.5, 0, 0]);
  line([
    [-w / 2, 0, -d / 2],
    [-w / 2 - off, 0, -d / 2],
    [-w / 2 - off, h, -d / 2],
    [-w / 2, h, -d / 2],
  ]);
  label(`${num(h)} mm`, [-w / 2 - off * 1.2, h * 0.5, -d / 2]);
  dimensions.visible = $("#show-dimensions").checked;
}
function renderFallback() {
  const p = state.project,
    m = p.metrics,
    w = m.outer_width_mm,
    d = m.outer_depth_mm,
    h = m.outer_height_mm;
  const points = (x, y, z) => [
    400 + (x - w / 2) * 0.55 - (y - d / 2) * 0.42,
    240 + (x - w / 2) * 0.19 + (y - d / 2) * 0.24 - z * 0.6,
  ];
  const polygon = (pts, fill) =>
    `<polygon points="${pts.map((p) => points(...p).join(",")).join(" ")}" fill="${fill}" stroke="#8e9299" stroke-width="1"/>`;
  $("#fallback").innerHTML =
    `<svg viewBox="0 0 800 450" aria-label="Isometric geometry fallback">${polygon(
      [
        [0, 0, 0],
        [w, 0, 0],
        [w, d, 0],
        [0, d, 0],
      ],
      "#c9bda6",
    )}${polygon(
      [
        [0, d, 0],
        [w, d, 0],
        [w, d, h],
        [0, d, h],
      ],
      "#d9cbb2",
    )}${polygon(
      [
        [w, 0, 0],
        [w, d, 0],
        [w, d, h],
        [w, 0, h],
      ],
      "#b9aa8f",
    )}<text x="400" y="425" text-anchor="middle" fill="#8a95a4" font-size="11">2D geometry preview · WebGL unavailable · ${num(w)} × ${num(d)} × ${num(h)} mm</text></svg>`;
}
function renderDrawing() {
  const p = state.project;
  if (p.drawing_svg) {
    $("#drawing-content").innerHTML = p.drawing_svg;
    return;
  }
  const m = p.metrics;
  const w = m.outer_width_mm,
    d = m.outer_depth_mm,
    h = m.outer_height_mm,
    t = p.spec.thickness_mm;
  const scale = Math.min(250 / w, 170 / d, 180 / h),
    W = w * scale,
    D = d * scale,
    H = h * scale,
    T = t * scale;
  const rect = (x, y, w, h, fill = "none") =>
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${fill}" stroke="#586578" stroke-width="1"/>`;
  const dim = (x1, y1, x2, y2, label) =>
    `<path d="M${x1},${y1} L${x2},${y2}" stroke="#a6b1bf" stroke-width=".6"/><text x="${(x1 + x2) / 2}" y="${(y1 + y2) / 2 - 5}" text-anchor="middle" fill="#65758a" font-size="8">${esc(label)}</text>`;
  const left = 65,
    top = 65,
    right = 400;
  let svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 620" role="img" aria-label="Orthographic panel crate drawings"><rect width="760" height="620" fill="white"/><rect x="22" y="22" width="716" height="576" fill="none" stroke="#c5cdd8"/><g font-family="Arial, sans-serif"><text x="50" y="45" font-size="9" fill="#8995a5">FORMA / PARAMETRIC DRAWING</text>`;
  svg += rect(left, top, W, D) + rect(left + T, top + T, W - 2 * T, D - 2 * T);
  svg +=
    dim(left, top - 2, left + W, top - 2, `${num(w)} mm`) +
    `<text x="${left}" y="${top + D + 24}" font-size="10" fill="#647186">TOP</text>`;
  svg +=
    rect(left, 320, W, H) +
    rect(
      left + T,
      320 + (p.spec.lid ? T : 0),
      W - 2 * T,
      H - T - (p.spec.lid ? T : 0),
    );
  svg +=
    dim(left, 320 + H + 16, left + W, 320 + H + 16, `${num(w)} mm`) +
    `<text x="${left}" y="${320 + H + 35}" font-size="10" fill="#647186">FRONT</text>`;
  svg +=
    rect(right, 320, D, H) +
    rect(
      right + T,
      320 + (p.spec.lid ? T : 0),
      D - 2 * T,
      H - T - (p.spec.lid ? T : 0),
    );
  svg +=
    dim(right, 320 + H + 16, right + D, 320 + H + 16, `${num(d)} mm`) +
    `<text x="${right}" y="${320 + H + 35}" font-size="10" fill="#647186">RIGHT</text>`;
  svg += `<g fill="#7d899b" font-size="9"><text x="400" y="95">INTERNAL CLEARANCE</text><text x="400" y="115">${num(p.spec.inner_width_mm)} × ${num(p.spec.inner_depth_mm)} × ${num(p.spec.inner_height_mm)} mm</text><text x="400" y="150">MATERIAL</text><text x="400" y="170">${esc(material().name)} · ${num(t)} mm</text><text x="400" y="205">HEIGHT: ${num(h)} mm</text><text x="400" y="225">${p.panels.length} panels · ${num(m.mass_kg, 2)} kg estimated</text></g><path d="M22 544 H738" stroke="#c5cdd8"/><text x="42" y="568" font-size="13" fill="#4f5e74">${esc(p.spec.name)}</text><text x="42" y="586" font-size="8" fill="#95a0b0">Dimensions in mm · Not to scale · Verify fabrication details and tolerances</text><text x="710" y="575" text-anchor="end" font-size="9" fill="#7e8b9f">${state.preview ? "PREVIEW" : esc(String(p.id || "").slice(0, 8))} / 01</text></g></svg>`;
  $("#drawing-content").innerHTML = svg;
}

async function sendPrompt() {
  const prompt = $("#prompt").value.trim();
  if (!prompt || state.busy || !state.saved) return;
  if (state.preview || inspectorDirty()) {
    toast(
      "Save or discard your design changes before requesting a Meta revision.",
      true,
    );
    return;
  }
  const previousJob =
    state.proposalContext?.base?.id === state.saved.id ? state.job : null;
  state.busy = true;
  state.job = null;
  state.proposal = null;
  state.proposalContext = { base: state.saved, jobId: null };
  $("#send-prompt").disabled = true;
  $("#agent-result").classList.remove("hidden");
  $("#agent-result").innerHTML =
    "<h3>Reading your design request…</h3><p>The model will propose a revision for review.</p>";
  $("#agent-status").textContent = "Working";
  try {
    const job = await api("/api/agent", {
      project_id: state.saved.id,
      prompt,
      previous_job_id: previousJob,
    });
    state.job = job.id;
    state.proposalContext.jobId = job.id;
    await pollJob(job.id);
  } catch (e) {
    showJobError(e);
  } finally {
    state.busy = false;
    $("#send-prompt").disabled = false;
  }
}
function showJobError(e) {
  $("#agent-result").innerHTML =
    `<h3>Request could not finish</h3><p>${esc(e.message)}</p>${state.job && !e.jobFailed ? '<p>No changes applied. The server request may still be running.</p><button id="resume-job">Check request status</button>' : ""}`;
  $("#agent-status").textContent = "Needs attention";
  $("#resume-job")?.addEventListener("click", async () => {
    if (state.busy) return;
    state.busy = true;
    $("#send-prompt").disabled = true;
    try {
      await pollJob(state.job);
    } catch (error) {
      showJobError(error);
    } finally {
      state.busy = false;
      $("#send-prompt").disabled = false;
    }
  });
}
async function pollJob(id) {
  const deadline = Date.now() + 150000;
  while (Date.now() < deadline) {
    const j = await api(
      `/api/jobs/${encodeURIComponent(id)}`,
      undefined,
      undefined,
      Math.min(15000, deadline - Date.now()),
    );
    if (state.job !== id) return;
    $("#agent-status").textContent = j.stage || j.status;
    if (j.status === "failed") {
      const e = new Error(
        j.error?.message || j.error || "Meta request failed.",
      );
      e.jobFailed = true;
      throw e;
    }
    if (j.status === "completed") {
      renderProposal(j);
      return;
    }
    const events = j.events || [];
    $("#agent-result").innerHTML =
      `<h3>${esc(j.stage || "Preparing proposal")}</h3>${events
        .slice(-3)
        .map((e) => `<p>${esc(e.message)}</p>`)
        .join("")}`;
    await new Promise((r) =>
      setTimeout(r, Math.min(1100, Math.max(0, deadline - Date.now()))),
    );
  }
  throw new Error("The request is taking longer than 150 seconds.");
}
function proposalComparison(p) {
  const before = state.proposalContext?.base?.metrics,
    after = p.result?.metrics;
  if (!before || !after || p.status === "clarify") return "";
  const envelope = (m) =>
    `${num(m.outer_width_mm)} × ${num(m.outer_depth_mm)} × ${num(m.outer_height_mm)}`;
  const rows = [
    ["Mass", `${num(before.mass_kg, 2)} kg`, `${num(after.mass_kg, 2)} kg`],
    [
      "Capacity",
      `${num(before.capacity_l, 2)} L`,
      `${num(after.capacity_l, 2)} L`,
    ],
    ["Envelope · mm", envelope(before), envelope(after)],
  ];
  return `<table class="proposal-comparison"><thead><tr><th></th><th>Current</th><th>Proposed</th></tr></thead><tbody>${rows.map((r) => `<tr>${r.map((v, i) => `<${i ? "td" : "th"}>${esc(v)}</${i ? "td" : "th"}>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function renderProposal(job) {
  const p = job.proposal;
  if (!p) throw new Error("The request completed without a proposal.");
  state.proposal = p;
  $("#agent-status").textContent =
    p.status === "ready"
      ? "Review proposal"
      : p.status === "clarify"
        ? "Needs clarification"
        : "Constraints not met";
  const changes = p.changes || p.result?.changes || [],
    checks =
      p.diagnostic_result?.checks ||
      (p.status === "clarify" ? [] : p.result?.checks || []),
    evidence = p.evidence || [];
  $("#agent-result").innerHTML =
    `<h3>${esc(p.summary || "Design proposal")}</h3>${proposalComparison(p)}${changes.length ? `<details class="proposal-details"><summary>${changes.length} design changes</summary><ul>${changes.map((c) => `<li><strong>${esc(readable(c.field))}</strong>: ${esc(c.before)} → ${esc(c.after)}</li>`).join("")}</ul></details>` : ""}${p.questions?.length ? `<p><strong>Clarification needed</strong></p><ul>${p.questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>` : ""}${checks.length ? `<details class="proposal-details"><summary>Verification · ${checks.filter((c) => c.status === "pass").length}/${checks.length} passed</summary>${checks.map((c) => `<p><span class="check-symbol ${c.status === "fail" ? "fail" : ""}">${checkSymbol(c)}</span> ${esc(c.label)}${c.detail ? " — " + esc(c.detail) : ""}</p>`).join("")}<p>Geometry and reference screening only; no physical qualification.</p></details>` : ""}${evidence.length || p.assumptions?.length ? `<details class="proposal-details"><summary>Source evidence & assumptions</summary>${evidence.map((e) => `<p><strong>${esc(readable(e.field))}</strong><br><q>${esc(e.quote)}</q></p>`).join("")}${(p.assumptions || []).map((a) => `<p>${esc(a)}</p>`).join("")}<p>Source excerpts establish provenance, not independent validation of intent.</p></details>` : ""}<div class="proposal-actions">${p.status === "ready" ? '<button id="preview-proposal">Preview design</button><button id="apply-proposal" class="primary">Apply revision</button>' : ""}<button id="dismiss-proposal">Dismiss</button><small>${esc(p.model || state.model.name || "Meta")}${p.estimated_cost_usd != null ? ` · ~$${Number(p.estimated_cost_usd).toFixed(4)} estimated` : ""}</small></div>`;
  $("#model-provenance").textContent =
    `${p.model || state.model.name || "Meta"} · ${p.status === "ready" ? "Proposal ready for approval" : "No changes applied"}`;
  $("#apply-proposal")?.addEventListener("click", applyProposal);
  $("#preview-proposal")?.addEventListener("click", () => {
    if (!guardProposal()) return;
    useProject(p.result, true);
    state.previewJob = job.id;
    $("#version-label").textContent = "Meta proposal preview · not applied";
    $("#model-provenance").textContent =
      `${p.model || state.model.name || "Meta"} · Preview only`;
    $("#save-project").textContent = "Save preview";
    setTab("model");
    toast("Previewing proposal. Apply revision to save with Meta provenance.");
  });
  $("#dismiss-proposal").addEventListener("click", () => {
    if (state.previewJob === job.id) useProject(state.saved);
    state.job = null;
    state.proposal = null;
    state.proposalContext = null;
    $("#agent-result").classList.add("hidden");
    $("#agent-status").textContent = "Ready";
    $("#model-provenance").textContent =
      `${p.model || state.model.name || "Meta"} · No proposal applied`;
  });
}
async function applyProposal() {
  if (state.applying || !guardProposal()) return;
  const b = $("#apply-proposal");
  if (b) b.disabled = true;
  state.applying = true;
  $("#save-project").disabled = true;
  try {
    const p = await api(
      `/api/proposals/${encodeURIComponent(state.job)}/apply`,
      {},
    );
    const stillCurrent = proposalCanApply();
    if (stillCurrent) useProject(p);
    await refreshHistory();
    $("#agent-result").innerHTML =
      `<h3>Revision applied</h3><p>${stillCurrent ? "The model, cut list and verification now reflect the saved design." : "The revision was saved in version history. Your newer workspace changes remain open."}</p>`;
    $("#agent-status").textContent = "Applied";
    $("#model-provenance").textContent =
      `${state.proposal?.model || state.model.name || "Meta"} · Revision applied`;
    $("#prompt").value = "";
    toast("Meta revision applied and saved.");
  } catch (e) {
    toast(e.message, true);
    if (b) b.disabled = false;
  } finally {
    state.applying = false;
    $("#save-project").disabled = false;
  }
}
async function exportFile(format) {
  if (state.preview || inspectorDirty()) {
    toast("Save or discard your design changes before exporting.", true);
    return;
  }
  if (!state.saved?.id) return;
  $("#export-options").classList.add("hidden");
  status(`Preparing ${format.toUpperCase()} export…`);
  try {
    const res = await fetch(
      `/api/projects/${encodeURIComponent(state.saved.id)}/export/${encodeURIComponent(format)}`,
    );
    if (!res.ok) {
      let message = await res.text();
      try {
        const j = JSON.parse(message);
        message = j.error?.message || j.error || j.detail || message;
      } catch {}
      throw new Error(message);
    }
    const blob = await res.blob(),
      url = URL.createObjectURL(blob);
    const header = res.headers.get("content-disposition") || "";
    const match = header.match(/filename="?([^";]+)"?/);
    const a = document.createElement("a");
    a.href = url;
    a.download = match
      ? match[1]
      : `${state.saved.spec.name || "forma-design"}.${format === "bundle" ? "zip" : format === "source" ? "py" : format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status("Export complete · project saved locally");
    toast(`${format.toUpperCase()} export downloaded.`);
  } catch (e) {
    toast(e.message, true);
    status("Export failed · see message");
  }
}
async function newProject() {
  if (!state.project) return;
  try {
    const p = await api("/api/projects", {
      spec: {
        name: "Untitled crate",
        inner_width_mm: 600,
        inner_depth_mm: 400,
        inner_height_mm: 300,
        thickness_mm: 12,
        material: "birch_plywood",
        lid: false,
      },
      requirements: {
        min_capacity_l: 72,
        max_outer_width_mm: 650,
        max_outer_depth_mm: 450,
        max_outer_height_mm: 350,
        max_mass_kg: 10,
        lock_inner_dimensions: true,
        objective: "minimize_mass",
        payload_kg: 0,
        max_floor_deflection_mm: 3,
      },
      label: "Initial design",
      source: "manual",
    });
    useProject(p);
    await refreshHistory();
    $("#agent-result").classList.add("hidden");
    toast("New project created.");
  } catch (e) {
    toast(e.message, true);
  }
}

$("#design-form").addEventListener("submit", (e) => {
  e.preventDefault();
  preview();
});
$("#save-project").addEventListener("click", saveProject);
$("#new-project").addEventListener("click", newProject);
$("#open-studio").addEventListener("click", () => {
  if (state.preview || inspectorDirty()) {
    toast("Save or discard the preview before opening CAD Studio.", true);
    return;
  }
  window.location.href = `/studio?crate=${encodeURIComponent(state.saved.id)}`;
});
$("#new-project-explorer").addEventListener("click", async () => {
  await newProject();
  closeDrawers();
});
$("#discard-preview").addEventListener("click", () => useProject(state.saved));
$("#refresh-history").addEventListener("click", () =>
  refreshHistory().catch((e) => toast(e.message, true)),
);
$("#export-menu").addEventListener("click", (e) => {
  e.stopPropagation();
  $("#export-options").classList.toggle("hidden");
});
document.addEventListener("click", (e) => {
  if (!e.target.closest(".menu-wrap"))
    $("#export-options").classList.add("hidden");
  const tab = e.target.closest("[data-tab]");
  if (tab) setTab(tab.dataset.tab);
  const part = e.target.closest("[data-part]");
  if (part) selectPart(part.dataset.part);
  const view = e.target.closest("[data-view]");
  if (view) fitView(view.dataset.view);
  const exp = e.target.closest("[data-export]");
  if (exp) exportFile(exp.dataset.export);
  const history = e.target.closest("[data-project]");
  if (history)
    api(`/api/projects/${encodeURIComponent(history.dataset.project)}`)
      .then((x) => {
        useProject(x);
        $("#agent-result").classList.add("hidden");
      })
      .catch((e) => toast(e.message, true));
});
$("#fit-view").addEventListener("click", () => fitView());
$("#explode").addEventListener("input", explode);
$("#show-wireframe").addEventListener("change", (e) =>
  meshes.forEach((m) => (m.material.wireframe = e.target.checked)),
);
$("#show-dimensions").addEventListener("change", explode);
$("#send-prompt").addEventListener("click", sendPrompt);
document.addEventListener("keydown", (e) => {
  const input = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    sendPrompt();
  }
  if (input) return;
  if (e.key.toLowerCase() === "f") fitView();
  if (["1", "2", "3"].includes(e.key))
    fitView({ 1: "front", 2: "top", 3: "right" }[e.key]);
  if (e.key === "Escape") selectPart(null);
});
const requirementFields = [
  ["min_capacity_l", "Minimum usable capacity", "L", 0.001],
  ["max_mass_kg", "Maximum empty mass", "kg", 0.001],
  ["max_outer_width_mm", "Maximum outer width", "mm", 0.001],
  ["max_outer_depth_mm", "Maximum outer depth", "mm", 0.001],
  ["max_outer_height_mm", "Maximum outer height", "mm", 0.001],
  ["payload_kg", "Uniform floor payload", "kg", 0],
  ["max_floor_deflection_mm", "Maximum floor deflection", "mm", 0.001],
];
$("#edit-requirements").addEventListener("click", () => {
  const r = state.requirements;
  $("#requirements-fields").innerHTML = requiredInputs(r);
  $("#requirements-error").textContent = "";
  $("#requirements-dialog").showModal();
});
function requiredInputs(r) {
  return (
    requirementFields
      .map(
        ([key, label, unit, min]) =>
          `<label class="field-label">${label} <span>${unit}</span><input type="number" data-requirement="${key}" value="${esc(r[key])}" min="${min}" step="any" required></label>`,
      )
      .join("") +
    `<label class="field-label">Design objective<select id="req-objective"><option value="minimize_mass" ${r.objective === "minimize_mass" ? "selected" : ""}>Minimize empty mass</option><option value="maximize_capacity" ${r.objective === "maximize_capacity" ? "selected" : ""}>Maximize usable capacity</option></select></label><label class="check-label requirement-lock"><input id="req-lock" type="checkbox" ${r.lock_inner_dimensions ? "checked" : ""}> Preserve internal dimensions when optimizing</label><p class="requirement-help">A zero payload disables floor-deflection screening. The screening model does not establish strength or a safe load rating.</p>`
  );
}
$("#save-requirements").addEventListener("click", async () => {
  const button = $("#save-requirements");
  try {
    const inputs = $$("[data-requirement]");
    if (inputs.some((x) => !x.reportValidity())) return;
    const r = { ...state.requirements };
    inputs.forEach((x) => (r[x.dataset.requirement] = Number(x.value)));
    r.objective = $("#req-objective").value;
    r.lock_inner_dimensions = $("#req-lock").checked;
    button.disabled = true;
    const result = await api("/api/design", {
      spec: formSpec(),
      requirements: r,
    });
    useProject(result, true);
    $("#requirements-dialog").close();
    toast("Requirements updated in preview. Save to keep them.");
  } catch (e) {
    $("#requirements-error").textContent = e.message;
  } finally {
    button.disabled = false;
  }
});
let optionRequest = 0;
const designContext = () =>
  JSON.stringify({
    revision: state.saved?.id,
    spec: formSpec(),
    requirements: state.requirements,
  });
$("#optimize-design").addEventListener("click", async () => {
  const button = $("#optimize-design"),
    note = $("#optimizer-note");
  const request = ++optionRequest,
    context = designContext();
  button.disabled = true;
  note.classList.remove("hidden");
  note.textContent = "Checking configured stock thicknesses…";
  try {
    const result = await api("/api/optimize", {
      spec: formSpec(),
      requirements: state.requirements,
    });
    if (request !== optionRequest || context !== designContext()) {
      note.textContent = "Design changed during search. Run comparison again.";
      return;
    }
    note.textContent = `${result.evaluated_count} candidates checked · ${result.candidates.length} feasible`;
    if (!result.candidates.length) {
      note.textContent +=
        ". No feasible design in the supported stock search family.";
      return;
    }
    const dialog = $("#design-options");
    $("#options-description").textContent =
      `${result.candidates.length} feasible alternatives · Ranked by ${state.requirements.objective === "maximize_capacity" ? "capacity" : "empty mass"}. Select one to preview before saving.`;
    $("#options-scope").textContent = result.explanation;
    $("#options-error").textContent = "";
    $("#options-list").innerHTML = result.candidates
      .map((c, i) => {
        const m = c.metrics;
        return `<article class="design-option"><div class="option-heading"><strong>${i === 0 ? "Recommended" : "Alternative " + i}</strong><span>${num(c.spec.thickness_mm)} mm stock</span></div><dl><div><dt>Empty mass</dt><dd>${num(m.mass_kg, 2)} kg</dd></div><div><dt>Clear capacity</dt><dd>${num(m.capacity_l, 2)} L</dd></div><div><dt>Outside dimensions</dt><dd>${num(m.outer_width_mm)} × ${num(m.outer_depth_mm)} × ${num(m.outer_height_mm)} mm</dd></div><div><dt>Mass margin</dt><dd>${num(c.requirements.max_mass_kg - m.mass_kg, 2)} kg</dd></div></dl><button type="button" class="full-button" data-option="${i}">Preview design ↗</button></article>`;
      })
      .join("");
    $("#options-list").onclick = async (event) => {
      const target = event.target.closest("[data-option]");
      if (!target || target.disabled) return;
      const buttons = [...$("#options-list").querySelectorAll("button")];
      buttons.forEach((b) => (b.disabled = true));
      try {
        if (context !== designContext())
          throw new Error(
            "Design changed. Close this comparison and search again.",
          );
        const candidate = result.candidates[Number(target.dataset.option)];
        const checked = await api("/api/design", {
          spec: candidate.spec,
          requirements: candidate.requirements,
        });
        if (!dialog.open || context !== designContext()) return;
        useProject(checked, true);
        dialog.close();
        note.textContent = "Selected alternative shown as an unsaved preview.";
        toast("Review the design and save to create a revision.");
      } catch (error) {
        $("#options-error").textContent = error.message;
      } finally {
        buttons.forEach((b) => (b.disabled = false));
      }
    };
    dialog.showModal();
  } catch (error) {
    note.textContent = error.message;
    toast(error.message, true);
  } finally {
    button.disabled = false;
  }
});
$("#import-project").addEventListener("click", () => $("#import-file").click());
$("#import-file").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    const data = JSON.parse(await file.text());
    const p = data.project || data;
    if (!p.spec)
      throw new Error(
        "Choose a Forma project JSON containing spec and requirements.",
      );
    const saved = await api("/api/projects", {
      spec: p.spec,
      requirements: p.requirements || {},
      label: `Imported ${p.spec.name || "design"}`,
      source: "import",
    });
    useProject(saved);
    await refreshHistory();
    toast("Project imported and saved locally.");
  } catch (err) {
    toast(err.message, true);
  } finally {
    e.target.value = "";
  }
});
function closeDrawers() {
  $$(".drawer-open").forEach((x) => x.classList.remove("drawer-open"));
  $$("[data-drawer]").forEach((x) => x.setAttribute("aria-expanded", "false"));
  $("#drawer-backdrop").classList.add("hidden");
}
$("#design-form").addEventListener("input", () => {
  if (!state.project) return;
  const dirty = inspectorDirty();
  $("#save-project").textContent = dirty
    ? state.previewJob
      ? "Save manual version"
      : "Save changes"
    : state.previewJob
      ? "Apply revision"
      : state.preview
        ? "Save preview"
        : "Save version";
  $("#discard-preview").classList.toggle("hidden", !state.preview && !dirty);
  if (dirty)
    status(
      "Property edits are not yet reflected in the model · preview or save",
    );
});
$$("[data-drawer]").forEach((b) =>
  b.addEventListener("click", () => {
    const panel = $(`.${b.dataset.drawer}-panel`),
      wasOpen = panel.classList.contains("drawer-open");
    closeDrawers();
    if (!wasOpen) {
      panel.classList.add("drawer-open");
      b.setAttribute("aria-expanded", "true");
      $("#drawer-backdrop").classList.remove("hidden");
    }
  }),
);
$$("[data-close-drawer]").forEach((b) =>
  b.addEventListener("click", closeDrawers),
);
$("#drawer-backdrop").addEventListener("click", closeDrawers);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeDrawers();
});
window.addEventListener("resize", () => {
  if (window.innerWidth > 1050) closeDrawers();
});
async function start() {
  const graphics = setup3D();
  try {
    const b = await api("/api/bootstrap");
    state.materials = b.materials || [];
    state.projects = b.projects || [];
    state.model = b.model || {};
    $("#material").innerHTML = state.materials
      .map((m) => `<option value="${esc(m.id)}">${esc(m.name)}</option>`)
      .join("");
    $("#model-provenance").textContent =
      `${state.model.name || "Meta model"} · ${state.model.configured ? "Connected" : "API key not configured"}`;
    await graphics;
    useProject(b.project);
    if (!state.model.configured) {
      $("#agent-status").textContent = "Not configured";
      $("#prompt").placeholder =
        "Configure the Meta API key on the server to request revisions. Manual design tools are available.";
    }
  } catch (e) {
    await graphics;
    status("Could not load design engine");
    $("#model-subtitle").textContent = "The local API is unavailable.";
    toast(e.message, true);
    $("#agent-status").textContent = "Offline";
  }
}
start();
