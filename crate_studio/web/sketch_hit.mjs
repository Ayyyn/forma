/** Hit-test editable XY profiles, including concave polyline boundaries. */
export function profileContains(params, x, y) {
  const dx = x - (params.cx || 0), dy = y - (params.cy || 0);
  if (params.shape === "circle") return Math.hypot(dx, dy) <= params.radius;
  if (params.shape === "rectangle")
    return Math.abs(dx) <= params.width / 2 && Math.abs(dy) <= params.depth / 2;
  if (params.shape !== "polyline" || !Array.isArray(params.points) || params.points.length < 3)
    return false;
  let inside = false;
  const points = params.points;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [ax, ay] = points[j], [bx, by] = points[i];
    // Treat points on a finite segment as selectable, including vertices.
    const cross = (dx - ax) * (by - ay) - (dy - ay) * (bx - ax);
    if (Math.abs(cross) <= 1e-9 && dx >= Math.min(ax,bx) - 1e-9 &&
        dx <= Math.max(ax,bx) + 1e-9 && dy >= Math.min(ay,by) - 1e-9 && dy <= Math.max(ay,by) + 1e-9)
      return true;
    if ((ay > dy) !== (by > dy) && dx < ax + (dy - ay) * (bx - ax) / (by - ay))
      inside = !inside;
  }
  return inside;
}
