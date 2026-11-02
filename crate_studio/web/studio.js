import { createWorkflow } from "/assets/workflow.js";
let workflow;
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)],
  clone = (x) => JSON.parse(JSON.stringify(x));

const esc = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );

const fmt = (n, d = 2) =>
  Number.isFinite(Number(n))
    ? Number(n).toLocaleString(undefined, { maximumFractionDigits: d })
    : "—";

const uid = () => `f-${crypto.randomUUID().slice(0, 10)}`;

const state = {
  snapshot: null,
  document: null,
  documents: [],
  capabilities: { feature_types: [] },
  feature: null,
  selection: [],
  busy: false,
  pending: false,
  measure: false,
  history: [],
  tab: "model",
  sketchTool: "select",
  historyAll: false,
};

let THREE,
  scene,
  camera,
  renderer,
  controls,
  group,
  faceGroup,
  grid,
  raycaster,
  pointer,
  meshes = [],
  faces = [],
  edges = [],
  pickEdges = [],
  edgeGroup,
  measureGroup,
  toastTimer,
  drawDrag = null,
  annotationDrag = null,
  gizmo,
  gizmoPivot,
  gizmoStart,
  gizmoBody,
  gizmoDragging = false;

const sketch = { scale: 3, cx: 0, cy: 0, width: 0, height: 0 };

const definitions = {
  box: {
    label: "Box",
    icon: "▣",
    params: {
      width: 80,
      depth: 60,
      height: 30,
      cx: 0,
      cy: 0,
      z: 0,
      operation: "add",
    },
    fields: [
      ["width", "Width", "number"],
      ["depth", "Depth", "number"],
      ["height", "Height", "number"],
      ["cx", "Center X", "number"],
      ["cy", "Center Y", "number"],
      ["z", "Start Z", "number"],
      ["operation", "Operation", "select", ["add", "new_body", "cut"]],
    ],
  },

  cylinder: {
    label: "Cylinder",
    icon: "◉",
    params: { radius: 25, height: 40, cx: 0, cy: 0, z: 0, operation: "add" },
    fields: [
      ["radius", "Radius", "number"],
      ["height", "Height", "number"],
      ["cx", "Center X", "number"],
      ["cy", "Center Y", "number"],
      ["z", "Start Z", "number"],
      ["operation", "Operation", "select", ["add", "new_body", "cut"]],
    ],
  },

  sketch_extrude: {
    label: "Extrude",
    icon: "▱",
    params: {
      shape: "rectangle",
      width: 60,
      depth: 40,
      height: 10,
      cx: 0,
      cy: 0,
      z: 0,
      operation: "add",
    },
    fields: [
      ["shape", "Profile", "select", ["rectangle", "circle", "polyline"]],
      ["width", "Width", "number"],
      ["depth", "Depth", "number"],
      ["radius", "Radius", "number"],
      ["height", "Extrusion height", "number"],
      ["cx", "Center X", "number"],
      ["cy", "Center Y", "number"],
      ["z", "Start Z", "number"],
      ["operation", "Operation", "select", ["add", "new_body", "cut"]],
      ["points", "Polyline points", "points"],
    ],
  },

  cut_hole: {
    label: "Hole",
    icon: "⊙",
    params: { radius: 8, depth: 60, x: 0, y: 0, z: -10 },
    fields: [
      ["radius", "Radius", "number"],
      ["depth", "Depth", "number"],
      ["x", "Center X", "number"],
      ["y", "Center Y", "number"],
      ["z", "Start Z", "number"],
    ],
  },

  fillet: {
    label: "Fillet",
    icon: "◜",
    params: { radius: 2, selector: "vertical" },
    fields: [
      ["radius", "Radius", "number"],
      ["selector", "Edges", "select", ["vertical", "all"]],
    ],
  },

  chamfer: {
    label: "Chamfer",
    icon: "◩",
    params: { distance: 2, selector: "vertical" },
    fields: [
      ["distance", "Distance", "number"],
      ["selector", "Edges", "select", ["vertical", "all"]],
    ],
  },

  transform: {
    label: "Transform",
    icon: "✥",
    params: { translation: [0, 0, 0], rotation: [0, 0, 0] },
    fields: [
      ["translation", "Translation", "vector"],
      ["rotation", "Rotation", "vector"],
    ],
  },

  linear_pattern: {
    label: "Pattern",
    icon: "▦",
    params: { count: 3, spacing: [100, 0, 0], fuse: false },
    fields: [
      ["count", "Instance count", "number"],
      ["spacing", "Spacing", "vector"],
      ["fuse", "Fuse touching instances", "boolean"],
    ],
  },

  mirror: {
    label: "Mirror",
    icon: "◧",
    params: { plane: "YZ", keep_original: true },
    fields: [
      ["plane", "Mirror plane", "select", ["XY", "XZ", "YZ"]],
      ["keep_original", "Keep original body", "boolean"],
    ],
  },

  mate: {
    label: "Align faces",
    icon: "⇥",
    params: {
      source_part_id: "",
      source_face: 0,
      target_part_id: "",
      target_face: 0,
      offset: 0,
      mode: "coincident",
    },
    fields: [
      ["source_part_id", "Moving body", "text"],
      ["source_face", "Moving face index", "number"],
      ["target_part_id", "Reference body", "text"],
      ["target_face", "Reference face index", "number"],
      ["offset", "Offset", "number"],
      ["mode", "Alignment", "select", ["coincident", "parallel"]],
    ],
  },

  import_step: {
    label: "Imported STEP",
    icon: "⬡",
    params: {},
    fields: [["asset_id", "Source asset", "readonly"]],
  },

  union: { label: "Union", icon: "⊞", params: {}, fields: [] },

  boolean_cut: {
    label: "Subtract",
    icon: "⊟",
    params: { target: 0, tool: 1 },
    fields: [
      ["target", "Target body index", "number"],
      ["tool", "Tool body index", "number"],
    ],
  },
  face_offset: {
    label: "Push/pull face",
    icon: "↥",
    params: { part_id: "", face_index: 0, distance: 5 },
    fields: [
      ["part_id", "Body", "text"],
      ["face_index", "Planar face index", "number"],
      ["distance", "Offset distance", "number"],
    ],
  },
};

const mechanicalPlacement = [["cx", "Position X", "number"], ["cy", "Position Y", "number"], ["z", "Position Z", "number"], ["axis", "Axis", "select", ["+Z", "-Z", "+X", "-X", "+Y", "-Y"]], ["operation", "Operation", "select", ["new_body", "add", "cut"]]];
const gearFields = [["module", "Module", "number"], ["teeth", "Teeth", "number"], ["pressure_angle", "Pressure angle", "number"], ["phase", "Tooth phase", "number"], ["backlash", "Backlash", "number"], ["clearance", "Root clearance", "number"], ["bore_diameter", "Bore diameter", "number"], ["bore_flat", "D-bore flat X (optional)", "optional-number"], ["bore_angle", "Bore angle", "number"]];
const threadFields = [["major_diameter", "Major diameter", "number"], ["root_diameter", "Root diameter (optional)", "optional-number"], ["pitch", "Pitch", "number"], ["length", "Length", "number"], ["starts", "Starts", "number"], ["hand", "Hand", "select", ["right", "left"]], ["profile", "Profile", "select", ["iso", "buttress"]], ["crest_width", "Crest width (optional)", "optional-number"], ["root_width", "Root width (optional)", "optional-number"], ["apex_offset", "Crest offset (optional)", "optional-number"]];
const gearDefaults = {module: 1, teeth: 20, pressure_angle: 20, phase: 0, backlash: 0, clearance: 0, bore_diameter: 0, bore_angle: 0, cx: 0, cy: 0, z: 0, axis: "+Z", operation: "new_body"};
const threadDefaults = {major_diameter: 6, pitch: 1, length: 10, starts: 1, profile: "iso", hand: "right", cx: 0, cy: 0, z: 0, axis: "+Z", operation: "new_body"};
Object.assign(definitions, {
  spur_gear: {label: "Spur gear", icon: "⚙", params: {...gearDefaults, thickness: 5}, fields: [...gearFields, ["thickness", "Thickness", "number"], ...mechanicalPlacement]},
  bevel_gear: {label: "Bevel gear", icon: "⚙", params: {...gearDefaults, cone_angle: 45, face_width: 4}, fields: [...gearFields, ["cone_angle", "Pitch cone angle", "number"], ["face_width", "Face width", "number"], ...mechanicalPlacement]},
  threaded_body: {label: "Helical thread", icon: "≋", params: {...threadDefaults, external: true, outer_diameter: 10, radial_clearance: 0}, fields: [...threadFields, ["external", "External thread", "boolean"], ["outer_diameter", "Nut outside diameter", "number"], ["radial_clearance", "Radial clearance", "number"], ...mechanicalPlacement]},
  socket_head_screw: {label: "Socket head screw", icon: "⌖", params: {...threadDefaults, head_height: 6, head_diameter: 10, socket_af: 5, socket_depth: 3}, fields: [...threadFields.filter(f=>f[0]!=="profile"), ["head_height", "Head height", "number"], ["head_diameter", "Head diameter", "number"], ["socket_af", "Socket across flats", "number"], ["socket_depth", "Socket depth", "number"], ...mechanicalPlacement]},
});

const scope = {
  spur_gear: "Native involute gear. Position is the bottom centre before axis rotation. Phase rotates teeth independently of the bore.",
  bevel_gear: "Position is the pitch cone apex. Axis points from the large base towards the apex. Mating gears share an apex; verify actual clearance and motion.",
  threaded_body: "Real helical geometry, clipped to its length. Lead equals pitch times starts. Internal clearance is radial. Geometric fit is not a manufacturing qualification.",
  socket_head_screw: "Head top is at the position; the shaft extends against the selected axis. Length excludes the head.",
  sketch_extrude:
    "An XY profile extruded along global Z. Added profiles combine with the existing result; cut profiles remove material.",
  cut_hole:
    "Cuts a cylinder along global +Z from the specified starting point.",
  fillet:
    "Rounds matching edges on the accumulated result. Large radii or incompatible topology can fail.",
  chamfer: "Bevels matching edges on the accumulated result.",
  transform:
    "Moves the selected body, or all bodies when no target is set. Rotation uses the global origin, then translation. Angles are in degrees.",
  linear_pattern: "Copies the accumulated result along the spacing vector.",
  mirror: "Reflects the accumulated result across a global principal plane.",
  mate: "Sequential planar-face alignment. This is not a simultaneous assembly constraint solver.",
  import_step:
    "Exact imported geometry. Add downstream operations to edit it; native feature history is not reconstructed.",
};

async function api(path, data, timeout = 90000) {
  const ctl = new AbortController(),
    timer = setTimeout(() => ctl.abort(), timeout);
  try {
    const r = await fetch(`/api/studio${path}`, {
      method: data === undefined ? "GET" : "POST",
      headers: data === undefined ? {} : { "Content-Type": "application/json" },
      body: data === undefined ? undefined : JSON.stringify(data),
      signal: ctl.signal,
    });
    const body = await r.json();
    if (!r.ok)
      throw new Error(
        typeof body.detail === "string"
          ? body.detail
          : body.error?.message ||
            body.error ||
            JSON.stringify(body.detail || body),
      );
    return body;
  } catch (e) {
    if (e.name === "AbortError")
      throw new Error(
        "The CAD operation timed out. Your last saved version is unchanged.",
      );
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function toast(message, error = false) {
  $("#toast").textContent = message;
  $("#toast").className = "toast" + (error ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("#toast").classList.add("hidden"), 5500);
}

function status(message) {
  $("#status-message").textContent = message;
}

function setBusy(b) {
  state.busy = b;
  $$(
    ".operation-tools button,#save-document,#import-document,#new-document,#undo,#redo,#update-feature",
  ).forEach((el) => (el.disabled = b));
  if (!b) updateHistoryButtons();
}

function acceptedTypes() {
  return state.capabilities.feature_types || [];
}

function useSnapshot(value) {
  const s = value.snapshot || value;
  if (!s.document || !s.geometry)
    throw new Error("The CAD engine returned an incomplete document.");
  state.snapshot = s;
  state.document = clone(s.document);
  state.document.features ||= [];
  state.document.annotations ||= [];
  state.document.display ||= {};
  state.pending = false;
  state.inspectorDirty = false;
  state.previewResults = null;
  state.agentPreview = false;
  $("#interference-result").classList.add("hidden");
  $("#save-document").textContent = "Save version";
  if (!state.document.features.some((f) => f.id === state.feature))
    state.feature = null;
  state.selection = [];
  renderAll();
  renderConfigurations();
  if (s.id) updateDocumentUrl();
  if (state.measure) renderMeasurement();
  workflow?.update(s);
}

function renderAll() {
  const d = state.document,
    s = state.snapshot;
  $("#document-name").value = d.name || "Untitled design";
  $("#tree-name").textContent = d.name || "Untitled design";
  $("#stage-title").textContent = d.name || "Untitled design";
  $("#document-state").textContent = state.pending
    ? "Unsaved edits · last valid geometry shown"
    : s.id
      ? `${s.label || "Saved version"} · ${String(s.id).slice(-8)}`
      : "Preview · save to retain";
  $("#feature-count").textContent = d.features.length;
  $("#body-count").textContent =
    `${s.metrics?.solid_count || 0} solid${s.metrics?.solid_count === 1 ? "" : "s"}`;
  $("#stage-subtitle").textContent = d.features.length
    ? `${d.features.length} features · ${s.metrics?.solid_count || 0} solids · mm`
    : "Create a primitive or draw a sketch to begin.";
  $("#body-color").value = d.display.color || "#a9b9cf";
  renderTree();
  renderInspector();
  renderSummary();
  renderHistory();
  renderFeedback();
  renderGeometry();
  renderDrawing();
  drawSketch();
  renderAnnotations();
  updateHistoryButtons();
  status(
    state.pending ? "Unsaved edits" : "CAD engine connected · local workspace",
  );
}

function renderTools() {
  const types = acceptedTypes();
  $("#operation-tools").innerHTML = Object.entries(definitions)
    .filter(
      ([t]) =>
        types.includes(t) &&
        !["import_step", "mate", "face_offset"].includes(t),
    )
    .map(
      ([t, d]) =>
        `<button data-add="${t}" title="${esc(d.label)}"><span>${d.icon}</span>${d.label}</button>${t === "cylinder" && types.includes("sketch_extrude") ? '<span class="tool-divider"></span><button id="start-sketch"><span>⌑</span>Sketch</button>' : ""}`,
    )
    .join("");
  $("#start-sketch")?.addEventListener("click", () => {
    setTab("sketch");
    setSketchTool("rectangle");
  });
  const exports = ["step", "stl", "json", "svg", "pdf", "dxf", "csv", "bundle"];
  $("#export-menu").innerHTML = exports
    .map(
      (f) =>
        `<button data-export="${f}">${{ step: "Solid geometry", stl: "Triangle mesh", json: "Portable project", svg: "Review drawing", pdf: "Drawing PDF", dxf: "Drawing DXF", csv: "Body list", bundle: "Design package" }[f]}<small>${f.toUpperCase()}</small></button>`,
    )
    .join("");
  $$('[data-sketch-tool="rectangle"],[data-sketch-tool="circle"]').forEach(
    (b) => (b.disabled = !types.includes("sketch_extrude")),
  );
}

function renderTree() {
  const results = state.previewResults || state.snapshot?.feature_results || [];
  $("#feature-tree").innerHTML =
    state.document.features
      .map((f, i) => {
        const r = results.find((x) => x.id === f.id || x.feature_id === f.id);
        return `<div class="feature-item ${state.feature === f.id ? "selected" : ""} ${f.suppressed ? "suppressed" : ""} ${r?.status === "error" || r?.status === "failed" || r?.status === "blocked" ? "error" : ""}" data-feature="${esc(f.id)}" tabindex="0" role="button" title="${esc(r?.error || "")}"><span class="feature-icon">${definitions[f.type]?.icon || "◇"}</span><span class="feature-label">${esc(f.name || definitions[f.type]?.label || f.type)}<small>${String(i + 1).padStart(2, "0")} · ${f.suppressed ? "Suppressed" : r?.status === "error" ? "Failed" : r?.status === "blocked" ? "Blocked" : esc(definitions[f.type]?.label || f.type)}</small></span><button data-suppress="${esc(f.id)}" title="${f.suppressed ? "Unsuppress" : "Suppress"} feature">${f.suppressed ? "◌" : "◉"}</button></div>`;
      })
      .join("") || '<p class="tree-help">No features yet.</p>';
}

function renderInspector() {
  const f = state.document?.features.find((x) => x.id === state.feature);
  let selected = "";
  if (state.selection.length) {
    const picked = state.selection[state.selection.length - 1];
    selected = `<div class="selected-geometry"><div class="section-title">SELECTED ${picked.kind === "edge" ? "EDGE" : "FACE"} <button id="clear-selection" title="Clear selection">×</button></div><p>${esc(picked.part_id || "Body")} · ${esc(picked.id)}</p>${picked.area_mm2 != null ? `<p>Area <strong>${fmt(picked.area_mm2)} mm²</strong></p>` : ""}${picked.length_mm != null ? `<p>Length <strong>${fmt(picked.length_mm)} mm</strong></p>` : ""}${picked.kind === "edge" ? '<button id="fillet-selected" class="small-button">Fillet edge</button><button id="chamfer-selected" class="small-button">Chamfer edge</button>' : ""}<button id="hide-selected" class="small-button">Hide body</button>${gizmo ? '<button id="translate-selected" class="small-button">Move body ✥</button>' : ""}<p class="parameter-note">${picked.kind === "edge" ? "Ctrl-click another edge on this body for a shared edit. Measure reports exact selected-edge distance." : "Ctrl-click a second planar face on another body to align."}</p>${canMate() ? '<button id="align-selected" class="small-button">Align these faces</button>' : ""}${acceptedTypes().includes("face_offset") && String(picked.geom_type || picked.type).toUpperCase() === "PLANE" ? '<div class="push-pull-row"><label>Offset · mm<input id="face-offset-distance" type="number" value="5" step="any"></label><button id="push-pull-face">Push / pull ↥</button></div><p class="parameter-note">Positive outward, negative inward. Creates an editable solid operation.</p>' : ""}</div>`;
  }

  if (!f) {
    $("#selection-inspector").innerHTML =
      selected +
      `<div class="inspector-empty"><span>◇</span><h2>${state.document.features.length ? "Refine your design." : "Shape your next idea."}</h2><p>${state.document.features.length ? "Select a feature in the explorer to edit its dimensions. Click faces to inspect area; use Measure for point distances." : "Add a primitive or sketch from the toolbar. Select a feature to refine dimensions and operations."}</p></div>${(state.document.display.hidden_parts || []).length ? '<button id="show-all-bodies">Show all hidden bodies</button>' : ""}`;
    wireSelection();
    return;
  }

  const def = definitions[f.type] || { label: f.type, fields: [] };
  const fields = def.fields.filter(([key]) => {
    if (
      ["fillet", "chamfer"].includes(f.type) &&
      f.params.edge_indices &&
      key === "selector"
    )
      return false;
    if (f.type !== "sketch_extrude") return true;
    return !(
      (["width", "depth"].includes(key) && f.params.shape !== "rectangle") ||
      (key === "radius" && f.params.shape !== "circle") ||
      (key === "points" && f.params.shape !== "polyline")
    );
  });

  $("#selection-inspector").innerHTML =
    selected +
    `<div class="section-title">${esc(def.label.toUpperCase())}<span>${esc(f.id.slice(-6))}</span></div><label class="field-label">Feature name<input id="feature-name" value="${esc(f.name || def.label)}" maxlength="100"></label><p class="feature-meta">Feature ${state.document.features.indexOf(f) + 1} of ${state.document.features.length}${f.suppressed ? " · Suppressed" : ""}</p><form id="feature-form">${fields.map((field) => fieldHTML(field, f.params)).join("")}${f.params.edge_indices ? `<p class="parameter-note">${f.params.edge_indices.length} selected edge(s) on ${esc(f.params.part_id)}. References follow this feature history.</p>` : ""}${scope[f.type] ? `<p class="parameter-note">${esc(scope[f.type])}</p>` : ""}<label class="field-check"><input id="feature-suppressed" type="checkbox" ${f.suppressed ? "checked" : ""}> Suppress feature</label><div class="inspector-actions"><button id="update-feature" type="submit" class="primary">Update feature</button><button type="button" id="delete-feature" class="danger" title="Delete feature">×</button></div><div class="feature-order"><button type="button" id="move-feature-up" ${state.document.features.indexOf(f) === 0 ? "disabled" : ""}>↑ Move up</button><button type="button" id="move-feature-down" ${state.document.features.indexOf(f) === state.document.features.length - 1 ? "disabled" : ""}>↓ Move down</button></div><button type="button" id="discard-edits" class="discard-button">Discard parameter edits</button></form>`;

  $("#feature-form").addEventListener("input", () => {
    state.inspectorDirty = true;
    $("#document-state").textContent =
      "Parameter edits · update feature to save";
  });
  $("#feature-form").addEventListener("submit", (e) => {
    e.preventDefault();
    updateFeature();
  });
  $("#delete-feature").addEventListener("click", () => deleteFeature(f.id));
  $("#move-feature-up").addEventListener("click", () => moveFeature(f.id, -1));
  $("#move-feature-down").addEventListener("click", () => moveFeature(f.id, 1));
  $("#discard-edits")?.addEventListener("click", () =>
    useSnapshot(state.snapshot),
  );
  $('[data-param="shape"]')?.addEventListener("change", (e) => {
    readFeatureForm(f);
    f.params.shape = e.target.value;
    if (f.params.shape === "circle") f.params.radius ??= 20;
    renderInspector();
  });
  wireSelection();
}

function fieldHTML([key, label, type, options], params) {
  const value = params[key];
  const optional = type === "optional-number";
  if (optional) type = "number";
  const unit =
    ["rotation", "phase", "pressure_angle", "cone_angle", "bore_angle"].includes(key)
      ? "deg"
      : type === "number" &&
          ![
            "count",
            "teeth",
            "starts",
            "source_face",
            "target_face",
            "face_index",
            "target",
            "tool",
          ].includes(key)
        ? "mm"
        : "";
  if (type === "boolean")
    return `<label class="field-check"><input data-param="${key}" data-type="boolean" type="checkbox" ${value ? "checked" : ""}>${esc(label)}</label>`;
  if (type === "vector")
    return `<div class="field-label">${label}<span class="field-row three">${["X", "Y", "Z"].map((axis, i) => `<label>${axis}<input data-vector="${key}" data-index="${i}" type="number" value="${value?.[i] ?? 0}" step="any" aria-label="${label} ${axis}" required></label>`).join("")}</span></div>`;
  if (type === "select")
    return `<label class="field-label">${label}<select data-param="${key}" data-type="text">${options.map((o) => `<option value="${o}" ${value === o ? "selected" : ""}>${o[0].toUpperCase() + o.slice(1)}</option>`).join("")}</select></label>`;
  if (type === "points")
    return `<label class="field-label">${label}<textarea data-param="${key}" data-type="points" placeholder="0,0; 50,0; 25,40">${esc((value || []).map((p) => p.join(", ")).join("; "))}</textarea></label><p class="parameter-note">XY points separated by semicolons. The outline closes automatically.</p>`;
  return `<label class="field-label">${label}${unit ? `<span class="input-unit">${unit}</span>` : ""}<input data-param="${key}" data-type="${optional ? "optional-number" : type}" type="${type === "number" ? "number" : "text"}" ${type === "readonly" ? "readonly" : ""} value="${esc(value ?? (type === "number" && !optional ? 0 : ""))}" ${type === "number" ? `step="any" ${optional ? '' : 'required'}` : ""}></label>`;
}

function readFeatureForm(f) {
  f.name =
    $("#feature-name")?.value.trim() || definitions[f.type]?.label || f.type;
  $$("[data-param]").forEach((el) => {
    const type = el.dataset.type;
    if (type === "readonly") return;
    if (type === "optional-number" && el.value === "") { delete f.params[el.dataset.param]; return; }
    f.params[el.dataset.param] =
      type === "boolean"
        ? el.checked
        : (type === "number" || type === "optional-number")
          ? Number(el.value)
          : type === "points"
            ? el.value
                .split(";")
                .filter((x) => x.trim())
                .map((p) => p.split(",").map(Number))
            : el.value;
  });
  $$("[data-vector]").forEach((el) => {
    f.params[el.dataset.vector] ||= [0, 0, 0];
    f.params[el.dataset.vector][Number(el.dataset.index)] = Number(el.value);
  });
  f.suppressed = $("#feature-suppressed")?.checked || false;
  cleanParams(f);
}

function cleanParams(f) {
  if (f.type === "sketch_extrude") {
    if (f.params.shape === "circle") {
      delete f.params.width;
      delete f.params.depth;
      delete f.params.points;
    } else if (f.params.shape === "rectangle") {
      delete f.params.radius;
      delete f.params.points;
    } else {
      delete f.params.width;
      delete f.params.depth;
      delete f.params.radius;
    }
  }
}

async function updateFeature() {
  const f = state.document.features.find((x) => x.id === state.feature);
  if (!f) return;
  readFeatureForm(f);
  await commitDocument(`Edit ${f.name}`);
}

async function addFeature(type, override) {
  if (state.busy || !acceptedTypes().includes(type)) return;
  if (state.inspectorDirty) {
    toast("Update or discard the current parameter edits first.", true);
    return;
  }
  const def = definitions[type];
  if (
    ["fillet", "chamfer"].includes(type) &&
    state.selection.some((x) => x.kind === "edge") &&
    !state.selection.every(
      (x) => x.kind === "edge" && x.part_id === state.selection[0].part_id,
    )
  ) {
    toast("Select edges from one body for this operation.", true);
    return;
  }
  if (
    ["fillet", "chamfer"].includes(type) &&
    state.selection.length &&
    state.selection.every(
      (x) => x.kind === "edge" && x.part_id === state.selection[0].part_id,
    )
  ) {
    override = {
      ...override,
      part_id: state.selection[0].part_id,
      edge_indices: [...new Set(state.selection.map((x) => x.edge_index))],
    };
  }
  const f = {
    id: uid(),
    type,
    name: `${def.label} ${state.document.features.filter((x) => x.type === type).length + 1}`,
    params: { ...clone(def.params), ...override },
    suppressed: false,
  };
  cleanParams(f);
  if (f.params.edge_indices) delete f.params.selector;
  state.document.features.push(f);
  state.feature = f.id;
  await commitDocument(`Add ${def.label}`);
}

async function commitDocument(label = "Design revision") {
  if (state.busy) return false;
  setBusy(true);
  state.pending = true;
  $("#document-state").textContent = "Evaluating geometry…";
  status("Rebuilding feature history…");
  try {
    const document = clone(state.document);
    const preview = await api("/preview", { document });
    state.previewResults = preview.feature_results;
    if (preview.document_valid === false)
      throw new Error(
        preview.feature_results?.find((x) => x.status === "error")?.error ||
          "Feature regeneration failed.",
      );
    const result = await api("/documents", {
      document,
      parent_id:
        (state.agentPreview ? state.agentBase?.id : state.snapshot?.id) ||
        undefined,
      label,
    });
    useSnapshot(result);
    await refreshHistory();
    toast(label + " saved.");
    return true;
  } catch (e) {
    state.pending = true;
    renderTree();
    renderInspector();
    $("#document-state").textContent = "Unsaved edits · geometry unchanged";
    showError(e.message);
    toast(e.message, true);
    return false;
  } finally {
    setBusy(false);
  }
}

async function deleteFeature(id) {
  if (state.busy) return;
  const f = state.document.features.find((x) => x.id === id);
  state.document.features = state.document.features.filter((x) => x.id !== id);
  state.feature = null;
  await commitDocument(`Delete ${f?.name || "feature"}`);
}

async function moveFeature(id, offset) {
  const i = state.document.features.findIndex((x) => x.id === id),
    next = i + offset;
  if (next < 0 || next >= state.document.features.length) return;
  const [f] = state.document.features.splice(i, 1);
  state.document.features.splice(next, 0, f);
  await commitDocument(`Reorder ${f.name}`);
}

function renderSummary() {
  const m = state.snapshot?.metrics || {},
    bounds = m.bounds_mm || [
      [0, 0, 0],
      [0, 0, 0],
    ];
  const sizes = bounds[1].map((v, i) => v - bounds[0][i]);
  $("#model-summary").innerHTML = [
    ["Solid bodies", m.solid_count || 0],
    ["Volume", `${fmt(m.volume_mm3)} mm³`],
    ["Surface area", `${fmt(m.surface_area_mm2)} mm²`],
    ["Bounds", sizes.map((v) => fmt(v)).join(" × ") + " mm"],
  ]
    .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`)
    .join("");
}

function renderFeedback() {
  const checks = state.snapshot?.checks || [],
    fails = checks.filter((c) => c.status === "fail" || c.passed === false),
    stale = checks.some((c) => c.status === "stale");
  $("#feedback-panel").classList.toggle("error", fails.length > 0);
  $("#feedback-title").textContent = fails.length
    ? "Review geometry checks"
    : stale
      ? "Requirements need review"
      : state.document.features.length
        ? "Geometry rebuilt"
        : "Ready to create";
  $("#feedback-summary").textContent = state.document.features.length
    ? `${checks.length} geometry checks · ${state.snapshot.metrics?.solid_count || 0} solids`
    : "Every feature is evaluated by the CAD engine.";
  $("#feedback-details").innerHTML =
    checks
      .map(
        (c) =>
          `<div class="check-row ${c.status === "fail" || c.passed === false ? "fail" : ""}"><span>${c.status === "fail" || c.passed === false ? "×" : c.status === "pass" ? "✓" : c.status === "stale" ? "!" : "i"}</span><div>${esc(c.label || c.name || c.id || "Check")}${c.detail ? "<br>" + esc(c.detail) : ""}</div></div>`,
      )
      .join("") +
    `<p>Geometry verification does not establish strength, material suitability or fabrication readiness.</p>`;
}

function showError(message) {
  $("#feedback-panel").classList.add("error");
  $("#feedback-title").textContent = "Feature could not rebuild";
  $("#feedback-summary").textContent = message;
  $("#feedback-details").classList.remove("hidden");
  $("#feedback-details").innerHTML =
    `<p class="error-note">${esc(message)}</p><button id="feedback-discard">Restore last saved design</button>`;
  $("#feedback-discard").addEventListener("click", () =>
    useSnapshot(state.snapshot),
  );
  status("Changes not saved · last valid geometry retained");
}

function updateDocumentUrl() {
  if (!state.snapshot?.id) return;
  const url = new URL(location.href);
  url.searchParams.delete("crate");
  url.searchParams.set("document", state.snapshot.id);
  url.searchParams.set("view", state.tab);
  history.replaceState(null, "", url.pathname + url.search);
}

function renderHistory() {
  const byId = new Map(state.documents.map((d) => [d.id, d]));
  const rootOf = (id) => {
    const seen = new Set();
    while (id && byId.get(id)?.parent_id && !seen.has(id)) {
      seen.add(id);
      id = byId.get(id).parent_id;
    }
    return id;
  };
  const root = rootOf(state.snapshot?.id || state.agentBase?.id);
  const rows =
    state.historyAll || !root
      ? state.documents
      : state.documents.filter((d) => rootOf(d.id) === root);
  $("#history-scope").textContent = state.historyAll
    ? "Show this project"
    : "Show all local designs";
  $("#version-history").innerHTML = rows
    .map(
      (d) =>
        `<button data-version="${esc(d.id)}" class="${d.id === state.snapshot?.id ? "active" : ""}">${esc(d.label || d.name || "Saved version")}<small>${esc(d.created_at ? new Date(d.created_at).toLocaleString(undefined, { timeZone: "Asia/Kolkata", timeZoneName: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : String(d.id).slice(-8))}</small></button>`,
    )
    .join("");
}
$("#history-scope").addEventListener("click", () => {
  state.historyAll = !state.historyAll;
  renderHistory();
});

async function refreshHistory() {
  const b = await api("/bootstrap");
  state.documents = b.documents || [];
  renderHistory();
  updateHistoryButtons();
}

function updateHistoryButtons() {
  const id = state.snapshot?.id;
  const entry = state.documents.find((d) => d.id === id);
  $("#undo").disabled =
    state.busy ||
    !(state.snapshot?.undo_id || state.snapshot?.parent_id || entry?.parent_id);
  $("#redo").disabled =
    state.busy ||
    !(
      state.snapshot?.redo_id || state.documents.some((d) => d.parent_id === id)
    );
}

async function undoRedo(direction) {
  if (state.busy || !state.snapshot?.id) return;
  if (state.pending && direction === "undo") {
    useSnapshot(state.snapshot);
    toast("Unsaved edits discarded.");
    return;
  }
  setBusy(true);
  try {
    const result = await api("/" + direction, {
      current_id: state.snapshot.id,
    });
    useSnapshot(result);
    await refreshHistory();
    toast(
      direction === "undo"
        ? "Previous version restored."
        : "Next version restored.",
    );
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(false);
  }
}

function setTab(tab) {
  state.tab = tab;
  updateDocumentUrl();
  $$("[data-tab]").forEach((x) =>
    x.classList.toggle("active", x.dataset.tab === tab),
  );
  $$(".tab-panel").forEach((x) =>
    x.classList.toggle("active", x.id === tab + "-tab"),
  );
  workflow?.tabChanged(tab);
  if (tab === "model") resize3D();
  if (tab === "sketch") {
    resizeSketch();
    drawSketch();
    renderAnnotations();
  }
}

function selectFeature(id) {
  if (state.inspectorDirty && id !== state.feature) {
    toast("Update or discard the current parameter edits first.", true);
    return;
  }
  state.feature = id;
  renderTree();
  renderInspector();
  $("#selection-message").textContent =
    state.document.features.find((f) => f.id === id)?.name ||
    "Nothing selected";
}

async function setup3D() {
  try {
    THREE = await import("/assets/vendor/three.module.js");
    const { OrbitControls } = await import("/assets/vendor/OrbitControls.js");
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(35, 1, 0.01, 1000000);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setClearColor(0, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    $("#viewport").append(renderer.domElement);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x7e91aa, 2.5));
    const light = new THREE.DirectionalLight(0xffffff, 3);
    light.position.set(300, 600, 400);
    scene.add(light);
    const fill = new THREE.DirectionalLight(0xc9d9f2, 1.2);
    fill.position.set(-300, 100, -200);
    scene.add(fill);
    group = new THREE.Group();
    faceGroup = new THREE.Group();
    edgeGroup = new THREE.Group();
    measureGroup = new THREE.Group();
    scene.add(group, faceGroup, edgeGroup, measureGroup);
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();
    let down;
    renderer.domElement.addEventListener(
      "pointerdown",
      (e) => (down = [e.clientX, e.clientY]),
    );
    renderer.domElement.addEventListener("pointerup", (e) => {
      if (down && Math.hypot(e.clientX - down[0], e.clientY - down[1]) < 5)
        pickGeometry(e);
    });
    new ResizeObserver(() => {
      resize3D();
      if (state.snapshot) fitView();
    }).observe($("#viewport"));
    renderer.setAnimationLoop(() => {
      if (state.tab !== "model" || document.hidden) return;
      controls.update();
      renderer.render(scene, camera);
    });
    resize3D();
    await setupGizmo();
  } catch (e) {
    $("#webgl-fallback").classList.remove("hidden");
    $("#webgl-fallback").textContent =
      "3D rendering is unavailable on this device. Feature editing and exports remain available.";
    console.warn(e.message);
  }
}

function dispose(g) {
  if (!g) return;
  while (g.children.length) {
    const x = g.children[0];
    x.traverse((o) => {
      o.geometry?.dispose();
      if (o.material)
        (Array.isArray(o.material) ? o.material : [o.material]).forEach((m) =>
          m.dispose(),
        );
    });
    g.remove(x);
  }
}

function geometry(data) {
  const g = new THREE.BufferGeometry(),
    v = [];
  for (let i = 0; i < data.vertices.length; i += 3)
    v.push(data.vertices[i], data.vertices[i + 2], -data.vertices[i + 1]);
  g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
  g.setIndex(data.triangles);
  g.computeVertexNormals();
  return g;
}
function buildPickEdges(data) {
  const metadata = state.snapshot.edge_meta || data.edge_meta || [],
    hidden = state.document.display.hidden_parts || [];
  for (const edge of metadata) {
    const points =
      edge.polyline_points ||
      (edge.type === "LINE" ? [edge.start, edge.end] : []);
    if (points.length < 2) continue;
    const g = new THREE.BufferGeometry().setFromPoints(
      points.map((p) => new THREE.Vector3(p[0], p[2], -p[1])),
    );
    const line = new THREE.Line(
      g,
      new THREE.LineBasicMaterial({
        color: 0x788fac,
        transparent: true,
        opacity: 0.65,
        depthTest: false,
      }),
    );
    line.userData = { ...edge, kind: "edge" };
    line.visible =
      $("#selection-mode").value === "edges" && !hidden.includes(edge.part_id);
    edgeGroup.add(line);
    pickEdges.push(line);
  }
}
$("#selection-mode").addEventListener("change", () => {
  state.selection = [];
  const hidden = state.document?.display.hidden_parts || [];
  pickEdges.forEach(
    (l) =>
      (l.visible =
        $("#selection-mode").value === "edges" &&
        !hidden.includes(l.userData.part_id)),
  );
  highlightSelection();
  renderInspector();
  if (state.measure) renderMeasurement();
  status(
    $("#selection-mode").value === "edges"
      ? "Pick edges · Ctrl-click to add a second edge"
      : "Pick faces · Ctrl-click a second face to align",
  );
});
async function setupGizmo() {
  try {
    const { TransformControls } = await import(
      "/assets/vendor/TransformControls.js"
    );
    gizmo = new TransformControls(camera, renderer.domElement);
    gizmo.setMode("translate");
    gizmo.setSpace("world");
    gizmo.setSize(0.8);
    gizmoPivot = new THREE.Object3D();
    scene.add(gizmoPivot, gizmo.getHelper());
    gizmo.addEventListener("dragging-changed", (e) => {
      gizmoDragging = e.value;
      controls.enabled = !e.value;
    });
    gizmo.addEventListener("mouseDown", () => {
      gizmoStart = gizmoPivot.position.clone();
    });
    gizmo.addEventListener("objectChange", () => {
      if (!gizmoDragging || !gizmoStart || !gizmoBody) return;
      const delta = gizmoPivot.position.clone().sub(gizmoStart);
      [...meshes, ...faces, ...pickEdges]
        .filter((m) => (m.userData.part_id || m.userData.id) === gizmoBody)
        .forEach((m) => m.position.copy(delta));
    });
    gizmo.addEventListener("mouseUp", async () => {
      if (!gizmoStart || !gizmoBody) return;
      const delta = gizmoPivot.position.clone().sub(gizmoStart),
        body = gizmoBody;
      [...meshes, ...faces, ...pickEdges]
        .filter((m) => (m.userData.part_id || m.userData.id) === body)
        .forEach((m) => m.position.set(0, 0, 0));
      gizmoStart = null;
      gizmo.detach();
      if (delta.length() > 0.001) {
        const translation = [delta.x, -delta.z, delta.y].map(
          (v) => Math.round(v * 1000) / 1000,
        );
        await addFeature("transform", {
          target_part_id: body,
          translation,
          rotation: [0, 0, 0],
        });
      }
    });
  } catch (e) {
    console.warn("Translation handles unavailable:", e.message);
  }
}
function translateSelected() {
  if (!gizmo || state.busy) return;
  if (state.inspectorDirty || state.pending) {
    toast("Update or discard parameter edits before moving a body.", true);
    return;
  }
  const id = state.selection.at(-1)?.part_id || state.selection.at(-1)?.id,
    mesh = meshes.find((m) => m.userData.id === id);
  if (!mesh) return;
  mesh.geometry.computeBoundingBox();
  gizmoPivot.position.copy(
    mesh.geometry.boundingBox.getCenter(new THREE.Vector3()),
  );
  gizmoBody = id;
  gizmoStart = null;
  gizmo.attach(gizmoPivot);
  closeDrawers();
  status("Drag a translation handle · release to save an editable transform");
}

function renderGeometry() {
  if (!renderer || !state.snapshot) return;
  gizmo?.detach();
  gizmoBody = null;
  dispose(group);
  dispose(faceGroup);
  dispose(edgeGroup);
  dispose(measureGroup);
  meshes = [];
  faces = [];
  edges = [];
  pickEdges = [];
  const data = state.snapshot.geometry || {},
    display = state.document.display || {};
  for (const p of data.parts || []) {
    const color = display.colors?.[p.id] || display.color || "#a9b9cf";
    const mesh = new THREE.Mesh(
      geometry(p),
      new THREE.MeshStandardMaterial({
        color,
        roughness: 0.55,
        metalness: 0.12,
        wireframe: $("#wireframe").checked,
      }),
    );
    mesh.userData = p;
    mesh.visible = !(display.hidden_parts || []).includes(p.id);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(mesh.geometry, 20),
      new THREE.LineBasicMaterial({
        color: 0x6f829e,
        transparent: true,
        opacity: 0.5,
      }),
    );
    edge.visible = $("#show-edges").checked;
    mesh.add(edge);
    edges.push(edge);
    group.add(mesh);
    meshes.push(mesh);
  }
  const faceData = state.snapshot.face_meshes || data.face_meshes || [];
  for (const f of faceData) {
    const mesh = new THREE.Mesh(
      geometry(f),
      new THREE.MeshBasicMaterial({
        color: 0x6e94e8,
        transparent: true,
        opacity: 0,
        side: THREE.DoubleSide,
        depthWrite: false,
        polygonOffset: true,
        polygonOffsetFactor: -1,
        polygonOffsetUnits: -1,
      }),
    );
    mesh.userData = { ...f, kind: "face" };
    mesh.visible = !(display.hidden_parts || []).includes(f.part_id);
    faceGroup.add(mesh);
    faces.push(mesh);
  }
  buildPickEdges(data);
  if (grid) {
    scene.remove(grid);
    grid.geometry.dispose();
    grid.material.dispose();
  }
  const b = state.snapshot.metrics?.bounds_mm || [
      [-50, -50, 0],
      [50, 50, 50],
    ],
    sizes = b[1].map((v, i) => v - b[0][i]),
    extent = Math.max(...sizes, 100) * 5;
  grid = new THREE.GridHelper(extent, 50, 0xc6d1e1, 0xe0e6ef);
  grid.position.y = Math.min(0, b[0][2]) - 0.02;
  grid.visible = $("#show-grid").checked;
  scene.add(grid);
  fitView();
}

function resize3D() {
  if (!renderer) return;
  const r = $("#viewport").getBoundingClientRect();
  if (!r.width || !r.height) return;
  camera.aspect = r.width / r.height;
  camera.updateProjectionMatrix();
  renderer.setSize(r.width, r.height);
}

function fitView(view) {
  if (!camera || !state.snapshot) return;
  const b = state.snapshot.metrics?.bounds_mm || [
      [-50, -50, 0],
      [50, 50, 50],
    ],
    c = b[0].map((v, i) => (v + b[1][i]) / 2),
    sizes = b[1].map((v, i) => v - b[0][i]);
  const radius = Math.max(Math.hypot(...sizes) / 2, 30),
    v = THREE.MathUtils.degToRad(camera.fov),
    h = 2 * Math.atan(Math.tan(v / 2) * camera.aspect),
    distance =
      (radius / Math.sin(Math.min(v, h) / 2)) *
      (innerWidth < 1050 ? 1.3 : 1.15);
  const name =
      view ||
      $$("[data-view]").find((b) => b.classList.contains("active"))?.dataset
        .view ||
      "iso",
    dir = {
      iso: [1.2, 0.95, 1.3],
      front: [0, 0.001, 1],
      top: [0, 1, 0.001],
      right: [1, 0.001, 0],
    }[name];
  controls.target.set(c[0], c[2], -c[1]);
  camera.position
    .copy(controls.target)
    .add(new THREE.Vector3(...dir).normalize().multiplyScalar(distance));
  camera.near = Math.max(0.01, distance / 10000);
  camera.far = Math.max(10000, distance * 100);
  camera.updateProjectionMatrix();
  controls.update();
  $$("[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name),
  );
}

function pickGeometry(e) {
  if (!renderer || !state.snapshot || gizmoDragging || gizmo?.axis) return;
  const r = renderer.domElement.getBoundingClientRect();
  pointer.set(
    ((e.clientX - r.left) / r.width) * 2 - 1,
    (-(e.clientY - r.top) / r.height) * 2 + 1,
  );
  raycaster.setFromCamera(pointer, camera);
  const edgeMode = $("#selection-mode").value === "edges";
  const bounds = state.snapshot.metrics.bounds_mm || [
    [0, 0, 0],
    [100, 100, 100],
  ];
  raycaster.params.Line.threshold = Math.max(
    0.1,
    Math.hypot(...bounds[1].map((v, i) => v - bounds[0][i])) * 0.006,
  );
  const hit = raycaster
    .intersectObjects(edgeMode ? pickEdges : faces.length ? faces : meshes)
    .find((x) => x.object.visible);
  if (!hit) {
    state.selection = [];
    highlightSelection();
    renderInspector();
    return;
  }
  const item = {
    ...hit.object.userData,
    point: [hit.point.x, -hit.point.z, hit.point.y],
    kind: edgeMode ? "edge" : faces.length ? "face" : "body",
  };
  if (e.ctrlKey || e.metaKey || state.measure) {
    state.selection.push(item);
    state.selection = state.selection.slice(-2);
  } else state.selection = [item];
  highlightSelection();
  renderInspector();
  $("#selection-message").textContent = `${item.kind} · ${item.id}`;
  if (state.measure) renderMeasurement();
}

function highlightSelection() {
  faces.forEach(
    (m) =>
      (m.material.opacity = state.selection.some((s) => s.id === m.userData.id)
        ? 0.38
        : 0),
  );
  pickEdges.forEach((m) => {
    const selected = state.selection.some((s) => s.id === m.userData.id);
    m.material.color.set(selected ? "#d58b43" : "#788fac");
    m.material.opacity = selected ? 1 : 0.65;
  });
}

function canMate() {
  return (
    acceptedTypes().includes("mate") &&
    state.selection.length === 2 &&
    state.selection.every(
      (s) =>
        s.kind === "face" &&
        s.face_index != null &&
        String(s.geom_type || s.type || "").toUpperCase() === "PLANE",
    ) &&
    state.selection[0].part_id !== state.selection[1].part_id
  );
}

function wireSelection() {
  $("#fillet-selected")?.addEventListener("click", () => addFeature("fillet"));
  $("#chamfer-selected")?.addEventListener("click", () =>
    addFeature("chamfer"),
  );
  $("#push-pull-face")?.addEventListener("click", () => {
    const p = state.selection.at(-1),
      distance = Number($("#face-offset-distance").value);
    if (!p || !Number.isFinite(distance) || distance === 0) {
      toast("Enter a nonzero offset in millimetres.", true);
      return;
    }
    addFeature("face_offset", {
      part_id: p.part_id,
      face_index: p.face_index,
      distance,
    });
  });
  $("#translate-selected")?.addEventListener("click", translateSelected);
  $("#clear-selection")?.addEventListener("click", () => {
    state.selection = [];
    highlightSelection();
    renderInspector();
  });
  $("#hide-selected")?.addEventListener("click", async () => {
    const id = state.selection.at(-1)?.part_id;
    if (!id) return;
    state.document.display.hidden_parts = [
      ...new Set([...(state.document.display.hidden_parts || []), id]),
    ];
    await commitDocument("Hide body");
  });
  $("#show-all-bodies")?.addEventListener("click", async () => {
    state.document.display.hidden_parts = [];
    await commitDocument("Show all bodies");
  });
  $("#align-selected")?.addEventListener("click", () => {
    if (!canMate()) return;
    const [s, t] = state.selection;
    addFeature("mate", {
      source_part_id: s.part_id,
      source_face: s.face_index,
      target_part_id: t.part_id,
      target_face: t.face_index,
      offset: 0,
      mode: "coincident",
    });
  });
}

async function renderMeasurement() {
  const card = $("#measurement-card");
  card.classList.remove("hidden");
  dispose(measureGroup);
  if (state.selection.length < 2) {
    card.innerHTML =
      "<span>Pick two surface points.</span><br><small>Distances follow the clicked mesh locations.</small>";
    return;
  }
  const [a, b] = state.selection;
  if (a.point && b.point) {
    const delta = b.point.map((v, i) => v - a.point[i]),
      distance = Math.hypot(...delta);
    card.innerHTML = `<strong>${fmt(distance)} mm</strong><span>Point-to-point distance</span><br><small>ΔX ${fmt(delta[0])} · ΔY ${fmt(delta[1])} · ΔZ ${fmt(delta[2])} mm</small>`;
    const pts = [a, b].map(
      (p) => new THREE.Vector3(p.point[0], p.point[2], -p.point[1]),
    );
    measureGroup.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: 0x577ecd, depthTest: false }),
      ),
    );
  }
  if (["face", "edge"].includes(a.kind) && ["face", "edge"].includes(b.kind)) {
    try {
      const result = await api("/measure", {
        document: state.document,
        selection: [a.id, b.id],
      });
      if (
        state.measure &&
        state.selection[0]?.id === a.id &&
        state.selection[1]?.id === b.id
      ) {
        const entries = Object.entries(result).filter(
          ([k, v]) => typeof v === "number",
        );
        if (entries.length)
          card.innerHTML += `<details><summary>Exact geometry measures</summary>${entries.map(([k, v]) => `<p>${esc(k.replace(/_/g, " "))}: ${fmt(v)}</p>`).join("")}</details>`;
      }
    } catch (e) {
      card.innerHTML += `<small>Exact geometry measure unavailable: ${esc(e.message)}</small>`;
    }
  }
}

function sketchToScreen(x, y) {
  return [
    sketch.width / 2 + (x - sketch.cx) * sketch.scale,
    sketch.height / 2 - (y - sketch.cy) * sketch.scale,
  ];
}

function screenToSketch(x, y, snap = true) {
  const p = [
    (x - sketch.width / 2) / sketch.scale + sketch.cx,
    -(y - sketch.height / 2) / sketch.scale + sketch.cy,
  ];
  if (snap && $("#snap-enabled").checked) {
    const step = Number($("#snap-step").value);
    return p.map((v) => Math.round(v / step) * step);
  }
  return p;
}

function resizeSketch() {
  const r = $("#sketch-surface").getBoundingClientRect();
  if (!r.width || !r.height) return;
  sketch.width = r.width;
  sketch.height = r.height;
  const c = $("#sketch-canvas");
  c.width = r.width * devicePixelRatio;
  c.height = r.height * devicePixelRatio;
  drawSketch();
  renderAnnotations();
}

function drawSketch() {
  const canvas = $("#sketch-canvas");
  if (!canvas.width) return;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  ctx.clearRect(0, 0, sketch.width, sketch.height);
  let spacing = Number($("#snap-step").value) * sketch.scale;
  while (spacing < 12) spacing *= 2;
  const [ox, oy] = sketchToScreen(0, 0);
  ctx.lineWidth = 0.6;
  ctx.strokeStyle = "#e1e7f0";
  ctx.beginPath();
  for (
    let x = ((ox % spacing) + spacing) % spacing;
    x < sketch.width;
    x += spacing
  ) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, sketch.height);
  }
  for (
    let y = ((oy % spacing) + spacing) % spacing;
    y < sketch.height;
    y += spacing
  ) {
    ctx.moveTo(0, y);
    ctx.lineTo(sketch.width, y);
  }
  ctx.stroke();
  ctx.strokeStyle = "#bfcddd";
  ctx.beginPath();
  ctx.moveTo(0, oy);
  ctx.lineTo(sketch.width, oy);
  ctx.moveTo(ox, 0);
  ctx.lineTo(ox, sketch.height);
  ctx.stroke();
  for (const f of state.document?.features || []) {
    if (f.type === "sketch_extrude" && !f.suppressed)
      drawProfile(ctx, f.params, f.id === state.feature);
  }
  if (drawDrag && drawDrag.tool !== "pan") {
    const [a, b] = [drawDrag.start, drawDrag.end];
    drawProfile(
      ctx,
      drawDrag.tool === "rectangle"
        ? {
            shape: "rectangle",
            cx: (a[0] + b[0]) / 2,
            cy: (a[1] + b[1]) / 2,
            width: Math.abs(b[0] - a[0]),
            depth: Math.abs(b[1] - a[1]),
          }
        : {
            shape: "circle",
            cx: a[0],
            cy: a[1],
            radius: Math.hypot(b[0] - a[0], b[1] - a[1]),
          },
      true,
      true,
    );
  }
}

function drawProfile(ctx, p, selected = false, ghost = false) {
  const [x, y] = sketchToScreen(p.cx || 0, p.cy || 0);
  ctx.strokeStyle = selected ? "#6b8ac8" : "#9baecb";
  ctx.fillStyle = selected ? "#89a9df20" : "#a9bed418";
  ctx.lineWidth = selected ? 1.7 : 1.1;
  ctx.setLineDash(ghost ? [5, 4] : []);
  ctx.beginPath();
  if (p.shape === "circle")
    ctx.arc(x, y, Math.abs(p.radius || 0) * sketch.scale, 0, Math.PI * 2);
  else if (p.shape === "polyline") {
    (p.points || []).forEach((point, i) => {
      const [px, py] = sketchToScreen(
        point[0] + (p.cx || 0),
        point[1] + (p.cy || 0),
      );
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    ctx.closePath();
  } else
    ctx.rect(
      x - ((p.width || 0) * sketch.scale) / 2,
      y - ((p.depth || 0) * sketch.scale) / 2,
      (p.width || 0) * sketch.scale,
      (p.depth || 0) * sketch.scale,
    );
  ctx.fill();
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#8d9fba";
  ctx.font = "9px Consolas,monospace";
  if (p.shape === "rectangle")
    ctx.fillText(`${fmt(p.width)} × ${fmt(p.depth)}`, x + 5, y - 7);
  if (p.shape === "circle") ctx.fillText(`R ${fmt(p.radius)}`, x + 5, y - 7);
}

function setSketchTool(tool) {
  state.sketchTool = tool;
  $$("[data-sketch-tool]").forEach((b) =>
    b.classList.toggle("active", b.dataset.sketchTool === tool),
  );
  $("#sketch-canvas").style.cursor =
    tool === "select" ? "default" : "crosshair";
  $("#sketch-help").textContent =
    tool === "select"
      ? "Click a profile to edit it. Middle-drag or Alt-drag to pan."
      : `Drag to draw a ${tool}. Creates an editable profile with a 10 mm extrusion.`;
}

const canvas = $("#sketch-canvas");
canvas.addEventListener("pointerdown", (e) => {
  if (state.busy) return;
  const r = canvas.getBoundingClientRect(),
    local = [e.clientX - r.left, e.clientY - r.top],
    world = screenToSketch(...local);
  canvas.setPointerCapture(e.pointerId);
  if (e.button === 1 || e.altKey) {
    drawDrag = { tool: "pan", screen: local, origin: [sketch.cx, sketch.cy] };
    return;
  }
  if (state.sketchTool === "select") {
    const candidates = state.document.features.filter(
      (f) => f.type === "sketch_extrude" && !f.suppressed,
    );
    const hit = candidates.reverse().find((f) => {
      const p = f.params,
        dx = world[0] - (p.cx || 0),
        dy = world[1] - (p.cy || 0);
      return p.shape === "circle"
        ? Math.hypot(dx, dy) < p.radius
        : p.shape === "rectangle"
          ? Math.abs(dx) < p.width / 2 && Math.abs(dy) < p.depth / 2
          : false;
    });
    if (hit) {
      selectFeature(hit.id);
      drawSketch();
    }
    return;
  }
  drawDrag = { tool: state.sketchTool, start: world, end: world };
  drawSketch();
});
canvas.addEventListener("pointermove", (e) => {
  const r = canvas.getBoundingClientRect(),
    local = [e.clientX - r.left, e.clientY - r.top],
    world = screenToSketch(...local);
  $("#sketch-coordinate").textContent =
    `X ${fmt(world[0], 1)} · Y ${fmt(world[1], 1)}`;
  if (drawDrag) {
    if (drawDrag.tool === "pan") {
      sketch.cx =
        drawDrag.origin[0] - (local[0] - drawDrag.screen[0]) / sketch.scale;
      sketch.cy =
        drawDrag.origin[1] + (local[1] - drawDrag.screen[1]) / sketch.scale;
      renderAnnotations();
    } else drawDrag.end = world;
    drawSketch();
  }
});
canvas.addEventListener("pointerup", async () => {
  const drag = drawDrag;
  drawDrag = null;
  if (!drag || drag.tool === "pan") return;
  const [a, b] = [drag.start, drag.end];
  if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 0.5) {
    drawSketch();
    return;
  }
  const params =
    drag.tool === "circle"
      ? {
          shape: "circle",
          cx: a[0],
          cy: a[1],
          radius: Math.hypot(b[0] - a[0], b[1] - a[1]),
        }
      : {
          shape: "rectangle",
          cx: (a[0] + b[0]) / 2,
          cy: (a[1] + b[1]) / 2,
          width: Math.abs(b[0] - a[0]),
          depth: Math.abs(b[1] - a[1]),
        };
  if (
    params.shape === "rectangle" &&
    (params.width < 0.1 || params.depth < 0.1)
  ) {
    drawSketch();
    return;
  }
  await addFeature("sketch_extrude", params);
});
canvas.addEventListener(
  "wheel",
  (e) => {
    e.preventDefault();
    sketch.scale = Math.min(
      40,
      Math.max(0.1, sketch.scale * (e.deltaY < 0 ? 1.1 : 0.91)),
    );
    drawSketch();
    renderAnnotations();
  },
  { passive: false },
);
new ResizeObserver(resizeSketch).observe($("#sketch-surface"));

let editingAnnotation = null;

function renderAnnotations() {
  const sheet = $("#drawing-sheet");
  if (!sheet || !state.document) return;
  sheet.querySelector(".annotation-hit-layer")?.remove();
  const svg = sheet.querySelector("svg");
  if (!svg) return;
  const notes = state.document.annotations || [];
  if (!notes.length) return;
  const layer = document.createElement("div");
  layer.className = "annotation-hit-layer";
  layer.innerHTML = notes
    .filter(
      (a) => !sheet.querySelector(`[data-annotation-id="${CSS.escape(a.id)}"]`),
    )
    .map(
      (a) =>
        `<div class="annotation-hit" data-annotation-id="${esc(a.id)}" style="left:${(a.x || 0) / 12}%;top:${((a.y || 0) - 14) / 8}%" title="Drag to move; double-click to edit">${esc(a.text || "Note")}</div>`,
    )
    .join("");
  sheet.append(layer);
}

function noteAtTarget(target) {
  const el = target.closest("[data-annotation-id]");
  return el
    ? {
        el,
        note: state.document.annotations.find(
          (a) => a.id === el.dataset.annotationId,
        ),
      }
    : null;
}

$("#drawing-sheet").addEventListener("pointerdown", (e) => {
  const hit = noteAtTarget(e.target);
  if (!hit?.note || state.busy) return;
  e.preventDefault();
  const rect = $("#drawing-sheet svg").getBoundingClientRect();
  annotationDrag = {
    id: hit.note.id,
    el: hit.el,
    x: e.clientX,
    y: e.clientY,
    origin: [hit.note.x, hit.note.y],
    sx: 1200 / rect.width,
    sy: 800 / rect.height,
    moved: false,
  };
  hit.el.setPointerCapture?.(e.pointerId);
});

$("#drawing-sheet").addEventListener("pointermove", (e) => {
  if (!annotationDrag) return;
  const a = annotationDrag,
    n = state.document.annotations.find((x) => x.id === a.id),
    dx = (e.clientX - a.x) * a.sx,
    dy = (e.clientY - a.y) * a.sy;
  n.x = Math.max(0, Math.min(1200, a.origin[0] + dx));
  n.y = Math.max(0, Math.min(800, a.origin[1] + dy));
  a.moved ||= Math.hypot(dx, dy) > 2;
  if (a.el instanceof SVGElement)
    a.el.setAttribute("transform", `translate(${dx} ${dy})`);
  else {
    a.el.style.left = n.x / 12 + "%";
    a.el.style.top = (n.y - 14) / 8 + "%";
  }
});

$("#drawing-sheet").addEventListener("pointerup", async () => {
  const drag = annotationDrag;
  annotationDrag = null;
  if (drag?.moved) await commitDocument("Move drawing note");
});

$("#drawing-sheet").addEventListener("dblclick", (e) => {
  const hit = noteAtTarget(e.target);
  if (!hit?.note) return;
  editingAnnotation = hit.note.id;
  $("#annotation-text").value = hit.note.text || "";
  $("#annotation-delete").classList.remove("hidden");
  $("#annotation-dialog").showModal();
});

$("#add-annotation").addEventListener("click", () => {
  editingAnnotation = null;
  $("#annotation-text").value = "";
  $("#annotation-delete").classList.add("hidden");
  $("#annotation-dialog").showModal();
});

$("#annotation-save").addEventListener("click", async () => {
  const text = $("#annotation-text").value.trim();
  if (!text) return;
  if (editingAnnotation) {
    const n = state.document.annotations.find(
      (x) => x.id === editingAnnotation,
    );
    if (n) n.text = text;
  } else
    state.document.annotations.push({
      id: uid(),
      type: "text",
      view: "sheet",
      text,
      x: 100,
      y: 520 + (state.document.annotations.length % 5) * 24,
    });
  $("#annotation-dialog").close();
  await commitDocument(
    editingAnnotation ? "Edit drawing note" : "Add drawing note",
  );
});

function renderDrawing() {
  const svg = state.snapshot?.drawing_svg;
  $("#drawing-sheet").innerHTML =
    svg ||
    '<p class="tree-help">Save a valid solid design to generate its review drawing.</p>';
  renderAnnotations();
}
$("#annotation-delete").addEventListener("click", async () => {
  if (!editingAnnotation) return;
  state.document.annotations = state.document.annotations.filter(
    (x) => x.id !== editingAnnotation,
  );
  $("#annotation-dialog").close();
  await commitDocument("Delete drawing note");
});
function renderConfigurations() {
  const list = Object.keys(state.document.configurations || {}),
    current = $("#configuration-select").value;
  $("#configuration-select").innerHTML =
    '<option value="">Select configuration…</option>' +
    list.map((n) => `<option value="${esc(n)}">${esc(n)}</option>`).join("");
  if (list.includes(current)) $("#configuration-select").value = current;
  $("#restore-configuration").disabled = !$("#configuration-select").value;
}
$("#configuration-select").addEventListener("change", () => {
  $("#restore-configuration").disabled = !$("#configuration-select").value;
});
$("#save-configuration").addEventListener("click", () => {
  $("#configuration-name").value = "";
  $("#configuration-error").classList.add("hidden");
  $("#configuration-dialog").showModal();
});
$("#confirm-configuration").addEventListener("click", async () => {
  const name = $("#configuration-name").value.trim();
  if (!name) return;
  const error = $("#configuration-error");
  if (state.inspectorDirty) {
    error.textContent = "Update the selected feature first.";
    error.classList.remove("hidden");
    return;
  }
  if (state.document.configurations?.[name]) {
    error.textContent =
      "This configuration name already exists. Choose a new name.";
    error.classList.remove("hidden");
    return;
  }
  state.document.configurations ||= {};
  state.document.configurations[name] = clone(state.document.features);
  $("#configuration-dialog").close();
  await commitDocument(`Save configuration: ${name}`);
});
$("#restore-configuration").addEventListener("click", async () => {
  const name = $("#configuration-select").value;
  if (!name || state.busy) return;
  if (state.inspectorDirty) {
    toast("Update or discard parameter edits first.", true);
    return;
  }
  state.document.features = clone(state.document.configurations[name]);
  state.feature = null;
  await commitDocument(`Restore configuration: ${name}`);
});
$("#check-interference").addEventListener("click", async () => {
  if (state.pending || state.inspectorDirty) {
    toast("Save the current edits before checking interference.", true);
    return;
  }
  const button = $("#check-interference"),
    out = $("#interference-result");
  button.disabled = true;
  out.classList.remove("hidden");
  out.textContent = "Computing exact body intersections…";
  try {
    const r = await api("/interference", { document: state.document });
    out.innerHTML = `<strong>${r.interference_count ? `${r.interference_count} intersecting body pair${r.interference_count === 1 ? "" : "s"}` : "No positive-volume intersections"}</strong>${r.pairs.map((p) => `<p>${p.parts.map(esc).join(" / ")}<br>${fmt(p.volume_mm3)} mm³ overlap</p>`).join("")}<p>${esc(r.scope)}</p>`;
  } catch (e) {
    out.textContent = e.message;
  } finally {
    button.disabled = false;
  }
});
async function sendAgent(regenerate = false) {
  const prompt = $("#agent-prompt").value.trim();
  if (!prompt || state.agentBusy || state.busy) return;
  if (state.pending || state.inspectorDirty || state.agentPreview) {
    toast(
      "Save or discard your current edits before requesting a proposal.",
      true,
    );
    return;
  }
  state.agentBusy = true;
  state.agentBase = clone(state.snapshot);
  state.agentProposal = null;
  state.agentJob = null;
  $("#agent-send").disabled = true;
  $("#agent-result").classList.remove("hidden");
  $("#agent-result").innerHTML =
    "<strong>Reading design intent…</strong><p>No changes will be applied without your review.</p>";
  $("#agent-status").textContent = "Working";
  try {
    const job = await api(
      "/agent",
      {
        document_id: state.snapshot.id,
        prompt,
        selection: state.selection
          .filter((x) => x.kind === "face" || x.kind === "edge")
          .map((x) => x.id)
          .slice(-2),
        selected_feature_id: state.feature || null,
        regenerate: regenerate === true,
      },
      30000,
    );
    state.agentJob = job.id;
    await pollAgent(job.id);
  } catch (e) {
    agentError(e);
  } finally {
    state.agentBusy = false;
    $("#agent-send").disabled = false;
  }
}
function agentError(e) {
  $("#agent-status").textContent = "Needs attention";
  $("#agent-result").innerHTML =
    `<strong>Request interrupted</strong><p>${esc(e.message)}</p>${state.agentJob && !e.failed ? '<button id="agent-resume">Check request status</button>' : ""}`;
  $("#agent-resume")?.addEventListener("click", async () => {
    if (state.agentBusy) return;
    state.agentBusy = true;
    $("#agent-send").disabled = true;
    try {
      await pollAgent(state.agentJob);
    } catch (error) {
      agentError(error);
    } finally {
      state.agentBusy = false;
      $("#agent-send").disabled = false;
    }
  });
}
async function pollAgent(id) {
  const end = Date.now() + 150000;
  while (Date.now() < end) {
    const job = await api(
      "/jobs/" + encodeURIComponent(id),
      undefined,
      Math.min(15000, end - Date.now()),
    );
    $("#agent-status").textContent = job.stage || job.status;
    if (job.status === "failed") {
      const e = new Error(job.error || "Meta request failed");
      e.failed = true;
      throw e;
    }
    if (job.status === "completed") {
      renderAgent(job);
      return;
    }
    $("#agent-result").innerHTML =
      `<strong>${esc(job.stage || "Preparing proposal")}</strong>${(
        job.events || []
      )
        .slice(-2)
        .map((e) => `<p>${esc(e.message)}</p>`)
        .join("")}`;
    await new Promise((r) =>
      setTimeout(r, Math.min(1100, Math.max(0, end - Date.now()))),
    );
  }
  throw new Error(
    "The request exceeded 150 seconds. Check its status to continue without another model call.",
  );
}
function agentStillCurrent() {
  if (!state.agentBase || state.inspectorDirty || state.pending) return false;
  const expected = state.agentPreview
    ? state.agentProposal?.document
    : state.agentBase.document;
  return (
    (state.agentPreview || state.snapshot?.id === state.agentBase.id) &&
    JSON.stringify(state.document) === JSON.stringify(expected)
  );
}
function describeChange(change) {
  if (typeof change === "string") return change;
  if (change.summary || change.description)
    return change.summary || change.description;
  const before = change.before || {},
    after = change.after || {};
  const feature =
    after.name ||
    before.name ||
    definitions[after.type || before.type]?.label ||
    "Feature";
  if (change.action === "add") return `Add ${feature}`;
  if (change.action === "delete") return `Delete ${feature}`;
  const edits = [];
  if (before.name !== after.name)
    edits.push(
      `Name: ${before.name || "Untitled"} → ${after.name || "Untitled"}`,
    );
  if (before.suppressed !== after.suppressed)
    edits.push(after.suppressed ? "Suppressed" : "Enabled");
  const fields = definitions[after.type || before.type]?.fields || [];
  const value = (v) =>
    Array.isArray(v)
      ? v.map((x) => (typeof x === "number" ? fmt(x, 3) : String(x))).join(", ")
      : v == null
        ? "Default"
        : typeof v === "number"
          ? fmt(v, 3)
          : typeof v === "boolean"
            ? v
              ? "Yes"
              : "No"
            : String(v);
  for (const key of new Set([
    ...Object.keys(before.params || {}),
    ...Object.keys(after.params || {}),
  ])) {
    const oldValue = before.params?.[key],
      newValue = after.params?.[key];
    if (JSON.stringify(oldValue) === JSON.stringify(newValue)) continue;
    const label =
      fields.find((f) => f[0] === key)?.[1] || key.replaceAll("_", " ");
    edits.push(`${label}: ${value(oldValue)} → ${value(newValue)}`);
  }
  return `${feature} · ${edits.join("; ") || "Update feature"}`;
}

function renderAgent(job) {
  const p = job.proposal;
  if (!p) throw new Error("No proposal returned.");
  state.agentProposal = p;
  $("#agent-status").textContent =
    p.status === "ready"
      ? "Review proposal"
      : p.status === "clarify"
        ? "Clarification needed"
        : "Geometry not valid";
  const b = state.agentBase.metrics || {},
    a = p.snapshot?.metrics || {};
  $("#agent-result").innerHTML =
    `<strong>${esc(p.summary || "Design proposal")}</strong>${p.status === "ready" ? `<div class="agent-comparison"><span>Volume</span><span>${fmt(b.volume_mm3)} → ${fmt(a.volume_mm3)} mm³</span><span>Solids</span><span>${b.solid_count || 0} → ${a.solid_count || 0}</span></div>` : ""}${p.questions?.length ? `<ul>${p.questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul>` : ""}${p.changes?.length ? `<details><summary>${p.changes.length} change${p.changes.length === 1 ? "" : "s"}</summary><ul>${p.changes.map((c) => `<li>${esc(describeChange(c))}</li>`).join("")}</ul></details>` : ""}${p.snapshot?.checks ? `<details><summary>Geometry verification</summary>${p.snapshot.checks.map((c) => `<p>${c.status === "pass" ? "✓" : c.status === "fail" ? "×" : "i"} ${esc(c.label)}${c.detail ? " — " + esc(c.detail) : ""}</p>`).join("")}</details>` : ""}<div class="agent-actions">${p.status === "ready" ? '<button id="agent-preview">Preview design</button><button id="agent-apply" class="primary">Apply revision</button>' : ""}<button id="agent-regenerate" title="Request a fresh model response">New proposal</button><button id="agent-dismiss">Dismiss</button><small>${p.cache?.hit ? "Reused verified proposal · " : ""}${esc(p.model || state.model?.name || "Meta")}${p.estimated_cost_usd != null ? " · ~$" + Number(p.estimated_cost_usd).toFixed(4) + " estimated" : ""}</small></div>`;
  $("#agent-provenance").textContent =
    `${p.model || "Meta"} · ${p.status === "ready" ? "Awaiting review" : "No changes applied"}`;
  $("#agent-preview")?.addEventListener("click", () => {
    if (!agentStillCurrent()) {
      toast(
        "The workspace changed. Request a new proposal for the active version.",
        true,
      );
      return;
    }
    useSnapshot(p.snapshot);
    state.agentPreview = true;
    $("#document-state").textContent = "Meta proposal preview · not applied";
    $("#save-document").textContent = "Apply revision";
    $("#agent-provenance").textContent = `${p.model || "Meta"} · Preview only`;
    setTab("model");
  });
  $("#agent-apply")?.addEventListener("click", applyAgent);
  $("#agent-regenerate").addEventListener("click", () => {
    if (state.agentPreview) { useSnapshot(state.agentBase); state.agentPreview = false; }
    if (!agentStillCurrent()) { toast("The workspace changed. Request a proposal for the active version.", true); return; }
    sendAgent(true);
  });
  $("#agent-dismiss").addEventListener("click", () => {
    if (state.agentPreview) useSnapshot(state.agentBase);
    $("#agent-result").classList.add("hidden");
    $("#agent-status").textContent = "Ready";
    $("#agent-provenance").textContent =
      `${p.model || "Meta"} · Proposal dismissed`;
    $("#save-document").textContent = "Save version";
  });
}
async function applyAgent() {
  if (state.agentApplying || !agentStillCurrent()) {
    toast(
      "The workspace changed. Request a new proposal for the active version.",
      true,
    );
    return;
  }
  state.agentApplying = true;
  setBusy(true);
  $("#agent-apply").disabled = true;
  try {
    const result = await api(
      "/proposals/" + encodeURIComponent(state.agentJob) + "/apply",
      {},
    );
    const current = agentStillCurrent();
    if (current) useSnapshot(result);
    await refreshHistory();
    $("#save-document").textContent = "Save version";
    $("#agent-status").textContent = "Applied";
    $("#agent-provenance").textContent =
      `${state.agentProposal.model || "Meta"} · Revision applied`;
    $("#agent-result").innerHTML =
      "<strong>Revision applied</strong><p>Saved as a new editable feature version.</p>";
    $("#agent-prompt").value = "";
    toast("Meta revision applied and saved.");
  } catch (e) {
    toast(e.message, true);
    $("#agent-apply")?.removeAttribute("disabled");
  } finally {
    state.agentApplying = false;
    setBusy(false);
  }
}
$("#agent-send").addEventListener("click", sendAgent);
$("#agent-prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    sendAgent();
  }
});

async function exportDocument(format) {
  $("#export-menu").classList.add("hidden");
  if (state.pending || state.inspectorDirty || state.agentPreview) {
    toast("Save or discard pending edits before exporting.", true);
    return;
  }
  if (!state.snapshot?.id) return;
  status(`Preparing ${format.toUpperCase()} export…`);
  try {
    const r = await fetch(
      `/api/studio/documents/${encodeURIComponent(state.snapshot.id)}/export/${format}`,
    );
    if (!r.ok) {
      const body = await r.json();
      throw new Error(body.detail || body.error || "Export failed");
    }
    const blob = await r.blob(),
      url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    const match = (r.headers.get("content-disposition") || "").match(
      /filename="?([^";]+)"?/,
    );
    a.download =
      match?.[1] ||
      `${state.document.name || "design"}.${format === "bundle" ? "zip" : format}`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status("Export downloaded");
    toast(format.toUpperCase() + " export downloaded.");
  } catch (e) {
    toast(e.message, true);
  }
}

async function importFile(file) {
  if (!file || state.busy) return;
  if (file.size > 15_000_000) {
    toast("Import supports files up to 15 MB.", true);
    return;
  }
  setBusy(true);
  status("Importing exact geometry…");
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let str = "";
    for (let i = 0; i < bytes.length; i += 32768)
      str += String.fromCharCode(...bytes.subarray(i, i + 32768));
    const result = await api("/import", {
      filename: file.name,
      content_base64: btoa(str),
      parent_id: state.snapshot?.id,
    });
    useSnapshot(result);
    await refreshHistory();
    toast("Imported " + file.name);
  } catch (e) {
    toast(e.message, true);
    showError(e.message);
  } finally {
    setBusy(false);
  }
}

function closeDrawers() {
  $$(".drawer-open").forEach((x) => x.classList.remove("drawer-open"));
  $("#drawer-backdrop").classList.add("hidden");
}
$("#show-bodies-global").addEventListener("click", async () => {
  if (state.busy) return;
  state.document.display.hidden_parts = [];
  await commitDocument("Show all bodies");
});

document.addEventListener("click", async (e) => {
  const target = e.target;
  const add = target.closest("[data-add]");
  if (add) addFeature(add.dataset.add);
  const tab = target.closest("[data-tab]");
  if (tab) setTab(tab.dataset.tab);
  const feature = target.closest("[data-feature]");
  const suppress = target.closest("[data-suppress]");
  if (suppress) {
    if (state.busy) return;
    const f = state.document.features.find(
      (x) => x.id === suppress.dataset.suppress,
    );
    f.suppressed = !f.suppressed;
    await commitDocument(`${f.suppressed ? "Suppress" : "Enable"} ${f.name}`);
  } else if (feature) selectFeature(feature.dataset.feature);
  const view = target.closest("[data-view]");
  if (view) fitView(view.dataset.view);
  const ex = target.closest("[data-export]");
  if (ex) exportDocument(ex.dataset.export);
  const ver = target.closest("[data-version]");
  if (ver && !state.busy) {
    try {
      useSnapshot(
        await api("/documents/" + encodeURIComponent(ver.dataset.version)),
      );
    } catch (error) {
      toast(error.message, true);
    }
  }
  const tool = target.closest("[data-sketch-tool]");
  if (tool) setSketchTool(tool.dataset.sketchTool);
  const drawer = target.closest("[data-drawer]");
  if (drawer) {
    const panel = $("." + drawer.dataset.drawer),
      open = panel.classList.contains("drawer-open");
    closeDrawers();
    if (!open) {
      panel.classList.add("drawer-open");
      $("#drawer-backdrop").classList.remove("hidden");
    }
  }
  if (target.closest("[data-close-drawer]")) closeDrawers();
  const del = target.closest("[data-delete-annotation]");
  if (del && !state.busy) {
    state.document.annotations = state.document.annotations.filter(
      (a) => a.id !== del.dataset.deleteAnnotation,
    );
    await commitDocument("Delete annotation");
  }
  if (!target.closest(".menu-wrap")) $("#export-menu").classList.add("hidden");
});

$("#export-toggle").addEventListener("click", () =>
  $("#export-menu").classList.toggle("hidden"),
);
$("#drawer-backdrop").addEventListener("click", closeDrawers);
$("#fit-view").addEventListener("click", () => fitView());
$("#show-grid").addEventListener("change", (e) => {
  if (grid) grid.visible = e.target.checked;
});
$("#wireframe").addEventListener("change", (e) =>
  meshes.forEach((m) => (m.material.wireframe = e.target.checked)),
);
$("#show-edges").addEventListener("change", (e) =>
  edges.forEach((x) => (x.visible = e.target.checked)),
);
$("#body-color").addEventListener("change", async (e) => {
  state.document.display.color = e.target.value;
  await commitDocument("Change display color");
});
$("#measure-toggle").addEventListener("click", () => {
  state.measure = !state.measure;
  state.selection = [];
  highlightSelection();
  $("#measure-toggle").classList.toggle("active", state.measure);
  $("#measurement-card").classList.toggle("hidden", !state.measure);
  if (state.measure) renderMeasurement();
  else dispose(measureGroup);
  renderInspector();
});
$("#toggle-checks").addEventListener("click", () =>
  $("#feedback-details").classList.toggle("hidden"),
);
$("#undo").addEventListener("click", () => undoRedo("undo"));
$("#redo").addEventListener("click", () => undoRedo("redo"));
$("#refresh-history").addEventListener("click", () =>
  refreshHistory().catch((e) => toast(e.message, true)),
);
$("#save-document").addEventListener("click", () => {
  if (state.agentPreview && !state.inspectorDirty) {
    applyAgent();
    return;
  }
  if (state.feature && $("#feature-form")) {
    const f = state.document.features.find((x) => x.id === state.feature);
    readFeatureForm(f);
  }
  commitDocument("Saved version");
});
$("#document-name").addEventListener("change", (e) => {
  state.document.name = e.target.value.trim() || "Untitled design";
  commitDocument("Rename document");
});
$("#new-document").addEventListener("click", async () => {
  if (state.busy) return;
  state.document = {
    name: "Untitled design",
    features: [],
    annotations: [],
    display: { color: "#a9b9cf", hidden_parts: [] },
  };
  state.feature = null;
  setBusy(true);
  try {
    useSnapshot(
      await api("/documents", {
        document: state.document,
        label: "New design",
      }),
    );
    await refreshHistory();
  } catch (e) {
    toast(e.message, true);
  } finally {
    setBusy(false);
  }
});
$("#new-document-explorer").addEventListener("click", () => {
  $("#new-document").click();
  closeDrawers();
});
$("#import-document").addEventListener("click", () =>
  $("#import-file").click(),
);
$("#import-file").addEventListener("change", (e) => {
  importFile(e.target.files[0]);
  e.target.value = "";
});
$("#sketch-plus").addEventListener("click", () => {
  sketch.scale = Math.min(40, sketch.scale * 1.25);
  drawSketch();
  renderAnnotations();
});
$("#sketch-minus").addEventListener("click", () => {
  sketch.scale = Math.max(0.1, sketch.scale / 1.25);
  drawSketch();
  renderAnnotations();
});
$("#sketch-fit").addEventListener("click", () => {
  const b = state.snapshot.metrics?.bounds_mm || [
    [-50, -50, 0],
    [50, 50, 0],
  ];
  sketch.cx = (b[0][0] + b[1][0]) / 2;
  sketch.cy = (b[0][1] + b[1][1]) / 2;
  sketch.scale =
    Math.min(
      sketch.width / Math.max(b[1][0] - b[0][0], 50),
      sketch.height / Math.max(b[1][1] - b[0][1], 50),
    ) * 0.6;
  drawSketch();
  renderAnnotations();
});
$("#snap-step").addEventListener("change", drawSketch);
document.addEventListener("keydown", (e) => {
  const text = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName);
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !text) {
    e.preventDefault();
    undoRedo(e.shiftKey ? "redo" : "undo");
  }
  if (text) return;
  if (e.key.toLowerCase() === "f") {
    if (state.tab === "canvas") workflow.fitCanvas();
    else fitView();
  }
  if (["1", "2", "3"].includes(e.key))
    fitView({ 1: "front", 2: "top", 3: "right" }[e.key]);
  if (e.key === "Escape") {
    closeDrawers();
    state.selection = [];
    gizmo?.detach();
    highlightSelection();
    renderInspector();
  }
  if (e.key === "Delete" && state.feature) deleteFeature(state.feature);
});
window.addEventListener("resize", () => {
  if (innerWidth > 1050) closeDrawers();
});

async function start() {
  const graphics = setup3D();
  try {
    const b = await api("/bootstrap");
    state.capabilities = b.capabilities || { feature_types: [] };
    state.documents = b.documents || [];
    state.model = b.model || {};
    $("#agent-provenance").textContent =
      `${state.model.name || "Meta"} · ${state.model.configured ? "Connected" : "Not configured"}`;
    renderTools();
    $("#import-file").accept = (
      state.capabilities.imports || ["step", "stp", "json"]
    )
      .map((x) => "." + x)
      .join(",");
    await graphics;
    const query = new URLSearchParams(location.search);
    const crate = query.get("crate"),
      documentId = query.get("document"),
      requestedView = query.get("view");
    const initial = crate
      ? await api("/from-crate/" + encodeURIComponent(crate), {})
      : documentId
        ? await api("/documents/" + encodeURIComponent(documentId))
        : b.document;
    useSnapshot(initial);
    if (crate) {
      await refreshHistory();
    }
    if (
      ["canvas", "project", "model", "sketch", "drawing", "motion"].includes(
        requestedView,
      )
    )
      setTab(requestedView);
    resizeSketch();
  } catch (e) {
    await graphics;
    showError(e.message);
    toast(e.message, true);
    status("Studio engine unavailable");
  }
}

workflow = createWorkflow({
  getState: () => state,
  api,
  toast,
  setTab,
  modelImage: () => {
    if (!renderer || !scene || !camera) return null;
    try {
      renderer.render(scene, camera);
      return renderer.domElement.toDataURL("image/png");
    } catch {
      return null;
    }
  },
  save: async (document, label) => {
    if (
      state.busy ||
      state.pending ||
      state.inspectorDirty ||
      state.agentPreview
    )
      throw new Error(
        "Finish pending CAD edits before saving project settings.",
      );
    const parent = state.snapshot?.id;
    setBusy(true);
    try {
      const result = await api("/documents", {
        document,
        parent_id: parent,
        label,
      });
      if (state.snapshot?.id !== parent)
        throw new Error(
          "Project changed while saving; the new revision is retained in history.",
        );
      useSnapshot(result);
      await refreshHistory();
      return result;
    } finally {
      setBusy(false);
    }
  },
});
start();
