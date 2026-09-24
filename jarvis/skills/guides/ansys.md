# Ansys (MAPDL via PyMAPDL) automation guide

Scripts run in Python with a live Ansys Mechanical APDL session. Pre-loaded: `mapdl` (every
APDL command is a method with the same name and arguments: `ET,1,BEAM188` is
`mapdl.et(1, "BEAM188")`, `/PREP7` is `mapdl.prep7()`, and anything else works via
`mapdl.run("APDL COMMAND")`), `an` (helpers), `np`. Units: SI throughout (m, N, Pa, kg, s).

## Helpers (pre-loaded as `an`)
- `an.new(title)` clear the database, set SI units, enter /PREP7. Call it to start a new model.
- `an.solve("STATIC"|"MODAL"|"TRANS"|"HARMIC", modes=6)` enter /SOLU, set the analysis type and solve.
  Steady-state thermal is also "STATIC" with thermal elements.
- `an.max_displacement("NORM"|"X"|"Y"|"Z")`, `an.max_stress()` (von Mises), `an.temperatures()`, `an.frequencies(6)`
- `an.plot("displacement"|"stress"|"temperature", path=None)` save a contour image, `an.save(name)`, `an.summary()`

## APDL essentials
Element types (`mapdl.et(1, name)`):
- 1D lines: `LINK180` (truss/bar, axial only), `BEAM188` (beam with a section), `PIPE288` (pipe),
  `LINK33` (1D heat conduction), `FLUID116` (1D thermal-fluid pipe flow: pressure and temperature DOFs;
  check its KEYOPTs and real constants in the element reference before relying on results)
- 2D: `PLANE182`/`PLANE183` (KEYOPT(3): 0 plane stress, 1 axisymmetric, 2 plane strain, 3 plane stress
  with thickness via `mapdl.r(1, t)`), `PLANE55`/`PLANE77` thermal
- Shells: `SHELL181` (`mapdl.sectype(1, "SHELL"); mapdl.secdata(thickness)`)
- 3D: `SOLID185`, `SOLID186` (quadratic hex), `SOLID187` (quadratic tet, best for free meshing), `SOLID70`/`SOLID90`/`SOLID87` thermal
Materials: `mapdl.mp("EX", 1, 200e9)`, `"PRXY"` 0.3, `"DENS"` 7850, `"KXX"` conductivity, `"C"` specific heat,
`"ALPX"` thermal expansion. Steel: E 200 GPa, nu 0.3, rho 7850. Aluminium: 69 GPa, 0.33, 2700.
Beam sections: `mapdl.sectype(1, "BEAM", "RECT"); mapdl.secdata(b, h)`; circle `"CSOLID"` (radius);
tube `"CTUBE"` (ri, ro); I-beam `"I"`.
Geometry: keypoints `mapdl.k(n, x, y, z)`, lines `mapdl.l(k1, k2)`, areas `mapdl.a(k1, k2, k3, k4)`,
primitives `mapdl.rectng(x1, x2, y1, y2)`, `mapdl.cyl4(xc, yc, r)`, `mapdl.block(x1, x2, y1, y2, z1, z2)`,
`mapdl.cylind(r1, r2, z1, z2)`, `mapdl.sphere(r)`. Booleans: `mapdl.asba(a1, a2)` (area minus area),
`mapdl.vsbv(v1, v2)`, `mapdl.aadd("ALL")`, `mapdl.vadd("ALL")`, `mapdl.vglue("ALL")`.
Direct nodes/elements: `mapdl.n(i, x, y, z)`, `mapdl.fill(n1, n2)`, `mapdl.e(n1, n2)`.
Meshing: `mapdl.esize(size)`, `mapdl.lesize("ALL", ndiv=20)`, `mapdl.smrtsize(4)`,
`mapdl.mshkey(0)` free / `1` mapped, `mapdl.mshape(1, "3D")` tets, then `mapdl.lmesh("ALL")` / `amesh` / `vmesh`.
Selecting (then apply loads to "ALL", then `mapdl.allsel()`): `mapdl.nsel("S", "LOC", "X", 0)`,
`mapdl.nsel("R", "LOC", "Y", 0.1)`, ranges `mapdl.nsel("S", "LOC", "X", 0.9, 1.0)`,
`mapdl.asel("S", "LOC", "Z", 0)`, `mapdl.nsla("S", 1)` nodes of selected areas.
Loads: fixed `mapdl.d("ALL", "ALL")`; one DOF `mapdl.d("ALL", "UY", 0)`; force `mapdl.f(node|"ALL", "FY", -1000)`;
pressure on areas `mapdl.sfa("ALL", 1, "PRES", 1e6)`; temperature `mapdl.d("ALL", "TEMP", 100)`;
convection `mapdl.sf("ALL", "CONV", h, T_bulk)`; heat generation `mapdl.bfe("ALL", "HGEN", 1, q)`; gravity `mapdl.acel(0, 9.81, 0)`.
Nodal forces on "ALL" apply to EACH selected node: divide a total load by `mapdl.mesh.n_node` of the selection
(`len(mapdl.mesh.nnum)` after selecting) or apply it at a single node.
Results: after `mapdl.post1(); mapdl.set("LAST")`: `mapdl.post_processing.nodal_displacement("Y")`,
`nodal_eqv_stress()`, `nodal_temperature()`, `nodal_component_stress("X")`; single values
`mapdl.get_value("NODE", n, "U", "Y")`; reaction forces `mapdl.fsum()` then `mapdl.get_value("FSUM", 0, "ITEM", "FY")`.
Always check results against a hand calculation when one exists, and print both.

## Recipe: cantilever beam (BEAM188) with a tip load
```python
an.new("Cantilever")
L, a, F, E = 1.0, 0.03, 1000.0, 200e9           # length m, square side m, load N, Young's modulus Pa
mapdl.et(1, "BEAM188")
mapdl.mp("EX", 1, E); mapdl.mp("PRXY", 1, 0.3); mapdl.mp("DENS", 1, 7850)
mapdl.sectype(1, "BEAM", "RECT"); mapdl.secdata(a, a)
mapdl.k(1, 0, 0, 0); mapdl.k(2, L, 0, 0); mapdl.l(1, 2)
mapdl.lesize("ALL", ndiv=20); mapdl.lmesh("ALL")
mapdl.nsel("S", "LOC", "X", 0); mapdl.d("ALL", "ALL"); mapdl.allsel()
mapdl.nsel("S", "LOC", "X", L); mapdl.f("ALL", "FY", -F); mapdl.allsel()
an.solve("STATIC")
uy = an.max_displacement("Y")
I = a**4 / 12
print(f"Theory F L^3 / 3EI = {F * L**3 / (3 * E * I):.6g} m")
an.max_stress(); an.save("cantilever")
```

## Recipe: 1D steady heat conduction through a rod (LINK33)
```python
an.new("Rod conduction")
L, A, k, n = 0.5, 1e-4, 50.0, 20
mapdl.et(1, "LINK33"); mapdl.r(1, A); mapdl.mp("KXX", 1, k)
mapdl.n(1, 0); mapdl.n(n + 1, L); mapdl.fill(1, n + 1)
for i in range(1, n + 1):
    mapdl.e(i, i + 1)
mapdl.d(1, "TEMP", 100); mapdl.d(n + 1, "TEMP", 20)
an.solve("STATIC")
T = an.temperatures()
print("Heat flow Q = k A dT / L =", k * A * 80 / L, "W")
```

## Recipe: 2D plate with a hole (stress concentration)
```python
an.new("Plate with hole")
W, H, r, t, sigma = 0.2, 0.1, 0.01, 0.005, 100e6
mapdl.et(1, "PLANE183", kop3=3); mapdl.r(1, t)
mapdl.mp("EX", 1, 200e9); mapdl.mp("PRXY", 1, 0.3)
mapdl.rectng(0, W, 0, H); mapdl.cyl4(W / 2, H / 2, r); mapdl.asba(1, 2)
mapdl.esize(r / 4); mapdl.amesh("ALL")
mapdl.nsel("S", "LOC", "X", 0); mapdl.d("ALL", "UX", 0); mapdl.allsel()
mapdl.nsel("S", "LOC", "Y", 0); mapdl.d("ALL", "UY", 0); mapdl.allsel()
mapdl.lsel("S", "LOC", "X", W); mapdl.sfl("ALL", "PRES", -sigma); mapdl.allsel()   # tension on the right edge
an.solve("STATIC"); an.max_stress()
print("Expected peak about 3 x nominal for a small hole in a wide plate")
```

## Recipe: natural frequencies (modal)
Build the model as usual (with density!), fix the supports, then `an.solve("MODAL", modes=6)` and
`an.frequencies(6)`.

## GUI: Workbench static structural analysis
1. Open Ansys Workbench. Drag Static Structural from the Toolbox onto the Project Schematic.
2. Engineering Data: add or edit materials. Geometry: right-click > New SpaceClaim/DesignModeler Geometry, or Import (STEP from SolidWorks).
3. Double-click Model to open Mechanical. Check the Mesh (set Element Size under Mesh details), Generate.
4. Static Structural: right-click > Insert > Fixed Support, Force, Pressure. Pick faces and set values.
5. Solution: right-click > Insert > Deformation > Total, Stress > Equivalent (von Mises). Click Solve.

## GUI: Fluent pipe flow (CFD)
1. Workbench: drag Fluid Flow (Fluent). Geometry: sketch a rectangle (radius x length) as a surface for
   2D axisymmetric, or a cylinder for 3D. Name the faces or edges: inlet, outlet, wall, axis.
2. Mesh: set the element size and add inflation layers on the wall. Update.
3. Setup (Fluent): General > 2D Space Axisymmetric (if 2D), Pressure-Based, Steady. Models > Viscous > Laminar
   (or k-omega SST if Re > 2300). Materials > water-liquid from the Fluent database.
4. Boundary Conditions: inlet = velocity-inlet (speed), outlet = pressure-outlet (0 Pa), wall = no slip, axis = axis.
5. Solution: Hybrid Initialization, Run Calculation with 300+ iterations. Watch the residuals.
6. Results: Contours of velocity/pressure; Plots > XY Plot along the axis; Reports > Surface Integrals for the pressure drop.
Pipe networks in 1D belong in Ansys Flownex or MAPDL FLUID116 elements. Fluent itself is 2D/3D.

## GUI: Mechanical APDL (classic)
1. Preprocessor > Element Type > Add; Material Props > Material Models; Modeling > Create; Meshing > MeshTool.
2. Solution > Define Loads > Apply > Structural > Displacement / Force; Solution > Solve > Current LS.
3. General Postproc > Plot Results > Contour Plot > Nodal Solu.
