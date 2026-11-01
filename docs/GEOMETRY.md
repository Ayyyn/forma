# Ideal panel geometry and independent checks

Coordinates use millimeters. Rows `r` and columns `c` count parallelogram facets, not four-facet Miura cells. Facet sides are `a,b`, sector angle `gamma`, and the folding parameter is `theta` from Schenk & Guest (2013). `theta=0` is planar; the prototype excludes `theta >= 89°`. An accordion is the orthogonal `gamma=90°` limiting construction.

Let `q = sqrt(1 - sin(theta)^2 sin(gamma)^2)`:

```
H = a sin(theta) sin(gamma)
L = a q
V = b cos(gamma) / q
S = b sin(gamma) cos(theta) / q
P(i,j) = (i L + (j mod 2) V, j S, (i mod 2) H)
```

Each quad is a parallelogram with edge vectors `(L,0,+/-H)` and `(+/-V,S,0)`. Their lengths are `a,b`, dot-product magnitude is `a b cos(gamma)`, and area is `a b sin(gamma)`. Consequently both diagonals, facet area, and coplanarity are invariant. All shared vertices are represented once. The finite sheet bounds are `(c L + V, r S, H)`; the chevron boundary overhang `V` must not be omitted.

The material area is `r c a b sin(gamma)`. Its projection onto the XY plane covers `r c L S = material_area cos(theta)`. This is smaller than the axis-aligned bounding rectangle; bounding area is not claimed to be usable coverage. This open sheet encloses no container volume.

Independent parameterization: set facet-edge tilt `psi = asin(sin(theta) sin(gamma))`. Derive `H=a sin(psi)`, `L=a cos(psi)`, `V=b cos(gamma)/cos(psi)`, `S=sqrt(b^2-V^2)` from rigid edge lengths and constant dot product. Tests compare these independently computed values against mesh extents.

For `0 <= theta < 89°` and `25° <= gamma <= 90°`, `L,S` are strictly positive. On each row strip, planar projection is `y=(j+t)S`, `x=(i+u)L + V[(1-t)(j mod 2)+t((j+1) mod 2)]`, for `0<=u,t<=1`. Its Jacobian is `L S > 0`. Row strips have disjoint y interiors and cells within a strip have disjoint x interiors, so projected facet interiors do not overlap. Thus the ideal sheet does not self-intersect along any continuous motion inside this domain. This is an analytic zero-thickness statement, not sampled collision detection and not finite-thickness clearance validation.

Exports use the same mesh at `theta=0`, with edge fold signs obtained from oriented adjacent face normals in a small positive folded state. SVG uses millimeter page dimensions and a 50 mm scale bar. FOLD vertices are explicitly in mm; deployed FOLD and crease-pattern FOLD use identical topology.

Physical correctness is a separate validation level: real paper facets bend, finite thickness limits packing, and folds have torque and springback. There is no load capacity, stability, exact packed thickness, or experimental performance claim.
