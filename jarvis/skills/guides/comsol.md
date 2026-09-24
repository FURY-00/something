# COMSOL Multiphysics automation guide

Scripts run in Python with a live COMSOL session (the `mph` library). Pre-loaded: `cs`
(helpers), `model` (current mph.Model or None), `jm` (the COMSOL Java API model =
`model.java`), `client`, `mph`, `np`. Everything in the COMSOL Java API ("Record Method",
"Save as Java") works through `jm` with Python syntax: Java `new String[]{"a","b"}` is a
Python list `["a", "b"]`, and `true` is `True`.

## Helpers (pre-loaded as `cs`)
- `model = cs.new_model(name)` create and make current; `model = cs.open(path)` load an .mph file
  (then `jm = model.java`)
- `cs.props(node)` dict of a node's property names and values (use it to discover names!)
- `cs.tags(node_list)` e.g. `cs.tags(jm.component("comp1").physics("spf").feature())`
- `cs.solve(study=None)`, `cs.evaluate(expr, unit=None, dataset=None)`, `cs.save(path=None)`
- `cs.export_image("pg1", path)` save a plot group as PNG; `cs.summary()` overview of the model
- mph itself: `model.parameter("L", "0.5[m]")`, `model.parameters()`, `model.build()`, `model.mesh()`,
  `model.solve("std1")`, `model.evaluate("T", "degC")` (numpy array), `model.save(path)`

## Model tree through the Java API
```python
jm.param().set("L", "1[m]", "Length")                 # global parameters
comp = jm.component().create("comp1", True)
geom = comp.geom().create("geom1", 3)                  # space dimension: 1, 2 or 3
# 2D axisymmetric: geom = comp.geom().create("geom1", 2); geom.axisymmetric(True)
```
Geometry features (then `geom.run()`):
- 1D: `geom.create("i1", "Interval")` then `.set("p1", "0")`, `.set("p2", "L")`; several segments:
  `.set("intervals", "many")`, `.set("coord", ["0", "0.5", "1"])`
- 2D: `"Rectangle"` (`size` [w, h], `pos` [x, y]), `"Circle"` (`r`, `pos`), `"Polygon"` (`x`, `y` lists or `table`)
- 3D: `"Block"` (`size` [a, b, c], `pos`), `"Cylinder"` (`r`, `h`, `pos`, `axis`), `"Sphere"` (`r`), `"Cone"`
- Booleans: `d = geom.create("dif1", "Difference"); d.selection("input").set(["blk1"]); d.selection("input2").set(["cyl1"])`;
  `"Union"`, `"Intersection"` use `selection("input")`; `"Fillet"`, `"Chamfer"` (2D), `"Extrude"`, `"Revolve"` from work planes
- Import CAD: `imp = geom.create("imp1", "Import"); imp.set("filename", path)` (STEP/STL/Parasolid need the CAD Import module)
- Numbers of domains/boundaries: `geom.getNDomains()`, `geom.getNBoundaries()`

Selections (which boundary is which). Numbers are fragile, so prefer **Box selections**:
```python
s = comp.selection().create("inlet", "Box")
s.set("entitydim", 1)          # 0 points, 1 edges (boundaries in 2D), 2 faces (boundaries in 3D)
s.set("xmin", "-1e-6"); s.set("xmax", "1e-6"); s.set("ymin", "-1"); s.set("ymax", "1")
s.set("condition", "inside")   # or "intersects", "allvertices"
feature.selection().named("inlet")
```
Direct numbers also work: `feature.selection().set([1, 3])`; everything: `feature.selection().all()`.
A 2D rectangle's boundaries are numbered 1 left, 2 bottom, 3 top, 4 right. A 1D interval's points are 1 (left), 2 (right).

Materials (no library needed: give the properties):
```python
mat = comp.material().create("mat1", "Common")
mat.label("Water")
mat.propertyGroup("def").set("density", "1000[kg/m^3]")
mat.propertyGroup("def").set("dynamicviscosity", "1e-3[Pa*s]")
mat.propertyGroup("def").set("thermalconductivity", "0.6[W/(m*K)]")
mat.propertyGroup("def").set("heatcapacity", "4180[J/(kg*K)]")
# solids: E and nu
mat.propertyGroup().create("Enu", "Young's modulus and Poisson's ratio")
mat.propertyGroup("Enu").set("E", "200e9[Pa]"); mat.propertyGroup("Enu").set("nu", "0.3")
mat.selection().all()
```
Physics interfaces (tag, type string): create with `comp.physics().create(tag, type, "geom1")`
- Solid Mechanics `"solid"`, `"SolidMechanics"`: features `"Fixed"`, `"BoundaryLoad"` (`FperArea` [fx, fy, fz]), `"BodyLoad"`, `"Roller"`
- Heat Transfer in Solids `"ht"`, `"HeatTransfer"`: `"TemperatureBoundary"` (`T0`), `"HeatFluxBoundary"` (`q0`), `"HeatSource"` (`Q0`)
- Laminar Flow `"spf"`, `"LaminarFlow"` (2D/3D): `"InletBoundary"` (`U0in`), `"OutletBoundary"` (`p0`), default wall `"wall1"`
- Pipe Flow (Pipe Flow Module, 1D edges) `"pfl"`, `"PipeFlow"`: default pipe/fluid property nodes; point features for inlet and outlet
- Transport of Diluted Species `"tds"`, `"DilutedSpecies"`: `"Concentration"`, `"Inflow"`, `"Outflow"`, `"Reactions"`
- Electric Currents `"ec"`, `"ConductiveMedia"`; Electrostatics `"es"`, `"Electrostatics"`; Magnetic Fields `"mf"`, `"InductionCurrents"`
- Pressure Acoustics `"acpr"`, `"PressureAcoustics"`; Coefficient Form PDE `"c"`, `"CoefficientFormPDE"`
- Boundary features: `f = phys.create("inl1", "InletBoundary", 1)` where the last number is the entity
  dimension (space dimension minus 1; in 1D it's 0 = points). Then `f.selection().set([...])` and `f.set("U0in", "0.1[m/s]")`.
- **Unsure about a feature or property name? Discover it**: `print(cs.tags(phys.feature()))`,
  `print(cs.props(phys.feature("pipe1")))`. Features and names vary with the COMSOL version and
  the licensed modules. A "Unknown feature" error means that type needs another module or has
  another name.
Multiphysics couplings: `comp.multiphysics().create("nitf1", "NonIsothermalFlow", 3)` (dimension = space dimension).

Mesh: `mesh = comp.mesh().create("mesh1"); mesh.autoMeshSize(5); mesh.run()` (1 = extremely fine ... 9 = extremely coarse).

Studies:
```python
std = jm.study().create("std1")
std.create("stat", "Stationary")                       # or:
# t = std.create("time", "Transient"); t.set("tlist", "range(0,0.1,10)")
# std.create("eig", "Eigenfrequency"); std.create("freq", "Frequency") with .set("plist", "range(100,100,1000)")
# sweep: p = std.create("param", "Parametric"); p.set("pname", ["L"]); p.set("plistarr", ["range(0.1,0.1,1)"])
model.solve("std1")
```
Results:
- Numbers: `model.evaluate("T", "degC")` gives an array over the mesh (use `np.max`, `np.mean`);
  point/boundary values need an operator: `op = comp.cpl().create("maxop1", "Maximum"); op.selection().all()`, then
  `model.evaluate("maxop1(T)", "degC")`; integrals: `"Integration"` operator (`intop1(...)`); averages: `"Average"`.
- Plots: `pg = jm.result().create("pg1", 2)` (dimension of the plot); `s = pg.create("surf1", "Surface"); s.set("expr", "T")`;
  1D: `lg = pg.create("lngr1", "LineGraph"); lg.set("expr", "p"); lg.selection().all()`; 3D: `"Volume"`, `"Slice"`; arrows `"ArrowSurface"`.
  `pg.run()`, then `cs.export_image("pg1", "~/Documents/Jarvis/Projects/comsol/plot.png")`.
- Always print the key numbers the user asked for, with units, and save the model with `cs.save()`.

## Recipe: 1D pipe flow (Pipe Flow Module)
```python
model = cs.new_model("pipe_1d")
jm = model.java
jm.param().set("L", "10[m]"); jm.param().set("D", "0.05[m]"); jm.param().set("dp", "2000[Pa]")
comp = jm.component().create("comp1", True)
geom = comp.geom().create("geom1", 1)
i1 = geom.create("i1", "Interval"); i1.set("p1", "0"); i1.set("p2", "L")
geom.run()
mat = comp.material().create("mat1", "Common")
mat.propertyGroup("def").set("density", "1000[kg/m^3]"); mat.propertyGroup("def").set("dynamicviscosity", "1e-3[Pa*s]")
mat.selection().all()
pfl = comp.physics().create("pfl", "PipeFlow", "geom1")
print("pipe flow features:", cs.tags(pfl.feature()))
for tag in cs.tags(pfl.feature()):
    print(tag, cs.props(pfl.feature(tag)))      # find the diameter / shape property names
# then: set the diameter on the pipe properties node, add an inlet (point 1) and a pressure
# condition (point 2), mesh, study, solve, evaluate "pfl.u" (velocity) and "p" (pressure).
```
Run this discovery part first, read the printed names, then finish the model in the next script.
Without the Pipe Flow Module, model 1D pressure-driven flow with a Coefficient Form PDE, or use
the 2D axisymmetric laminar pipe flow recipe below (base licence).

## Recipe: laminar flow in a pipe, 2D axisymmetric (base licence)
```python
model = cs.new_model("pipe_axisym")
jm = model.java
jm.param().set("R", "0.01[m]"); jm.param().set("L", "0.2[m]"); jm.param().set("Uin", "0.05[m/s]")
comp = jm.component().create("comp1", True)
geom = comp.geom().create("geom1", 2); geom.axisymmetric(True)
r = geom.create("r1", "Rectangle"); r.set("size", ["R", "L"]); geom.run()   # r along x, z along y
mat = comp.material().create("mat1", "Common")
mat.propertyGroup("def").set("density", "1000[kg/m^3]"); mat.propertyGroup("def").set("dynamicviscosity", "1e-3[Pa*s]")
mat.selection().all()
spf = comp.physics().create("spf", "LaminarFlow", "geom1")
inl = spf.create("inl1", "InletBoundary", 1); inl.selection().set([2]); inl.set("U0in", "Uin")   # bottom edge
out = spf.create("out1", "OutletBoundary", 1); out.selection().set([3])                          # top edge
mesh = comp.mesh().create("mesh1"); mesh.autoMeshSize(4)
std = jm.study().create("std1"); std.create("stat", "Stationary")
model.solve("std1")
U = model.evaluate("spf.U", "m/s")
print("max velocity:", float(np.max(U)), "m/s (Hagen-Poiseuille predicts about 2 * Uin)")
cs.save()
```
Boundary 1 is the symmetry axis (r = 0) and 4 is the wall, which gets the default no-slip wall.
The fully developed peak velocity should approach 2 * Uin (Hagen-Poiseuille): a good check.

## Recipe: 1D heat conduction in a rod
Geometry: `Interval` 0..L. Physics `"HeatTransfer"` (tag "ht"). Set the material thermal conductivity,
density and heat capacity. `TemperatureBoundary` on point 1 (T0 = 100[degC]) and point 2 (T0 = 20[degC]),
entity dimension 0. Stationary study. The analytic answer is a straight line between the two temperatures.

## Recipe: cantilever beam stress (3D, base licence)
Geometry: `Block` size ["L", "b", "h"]. Material with density, E and nu. `"SolidMechanics"` with `Fixed` on
the face at x = 0 (Box selection, entitydim 2) and `BoundaryLoad` on the face at x = L with
`FperArea` ["0", "0", "-F/(b*h)"]. Stationary study. Check the tip deflection against F L^3 / (3 E I).

## GUI: model wizard (start any model)
1. File > New > Model Wizard. Pick the space dimension: 3D, 2D axisymmetric, 2D, 1D axisymmetric, 1D or 0D.
2. Pick the physics (e.g. Fluid Flow > Single-Phase Flow > Laminar Flow, or Fluid Flow > Pipe Flow), click Add, then Study.
3. Pick the study type (Stationary, Time Dependent, Eigenfrequency, Frequency Domain) and Done.

## GUI: 1D pipe flow
1. Model Wizard > 1D (or 3D for a pipe network drawn as lines) > Fluid Flow > Pipe Flow > Stationary.
2. Global Definitions > Parameters: add L, D, inlet flow or pressure.
3. Geometry: add an Interval from 0 to L (in 3D: Polygon or Line segments for the network). Build All.
4. Materials: Add Material > Built-in > Water, liquid. Or a blank material with density and dynamic viscosity.
5. Pipe Flow > Pipe Properties: set the shape (Circular) and the inner diameter D; the friction model (e.g. Churchill).
6. Right-click Pipe Flow: add Inlet (point at the start, mass flow or velocity) and Pressure (point at the end).
7. Mesh: the default Normal is fine. Study > Compute. Results: line graphs of pressure and velocity along the pipe.

## GUI: geometry, materials and boundary conditions
1. Geometry: right-click Geometry 1 to add primitives (Block, Cylinder, Rectangle, Circle, Interval), set sizes, Build All.
   Booleans and Partitions > Difference/Union to combine. Import for CAD files.
2. Materials: right-click Materials > Add Material from Library, or Blank Material and type the properties.
3. Physics: right-click the physics node to add boundary conditions and pick boundaries in the Graphics window.

## GUI: mesh, solve and results
1. Mesh 1: Element size (Normal, Fine...) or add Free Tetrahedral, Mapped or Swept meshes. Build All.
2. Study 1 > Compute (F8). For sweeps, right-click Study 1 > Parametric Sweep, add the parameter and its range.
3. Results: default plots appear automatically. Right-click a plot group to add Surface, Line Graph or Arrow plots.
   Derived Values > Point Evaluation / Surface Integration give numbers. Export > Image saves pictures.

## GUI: learn the exact API for any step
Developer tab > Record Method. Do the step in the GUI, then Stop Recording. The method shows the exact
Java calls, which work unchanged through `jm` here. File > Save As > Model File for Java (*.java) exports a
whole model as API calls.
