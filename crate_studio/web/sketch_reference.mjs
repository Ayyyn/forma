import {BufferGeometry, Float32BufferAttribute, EdgesGeometry} from "./vendor/three.module.js";

export function savedSketchCount(document) {
  return (document?.features || []).filter(f => f.type === "sketch_extrude" && !f.suppressed).length;
}

// Visible mesh hard edges projected into XY. These are reference lines, not
// reconstructed CAD sketches, constraints, or an exact native drawing.
export function referenceSegments(parts) {
  const segments = [];
  for (const part of parts || []) {
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new Float32BufferAttribute(part.vertices, 3));
    geometry.setIndex(part.triangles);
    const edges = new EdgesGeometry(geometry);
    const positions = edges.attributes.position.array;
    for (let i = 0; i < positions.length; i += 6) {
      const [x1,y1,,x2,y2] = positions.slice(i,i+6);
      if (Math.hypot(x2-x1,y2-y1) > 1e-7) segments.push([x1,y1,x2,y2]);
    }
    edges.dispose();
    geometry.dispose();
  }
  return segments;
}
