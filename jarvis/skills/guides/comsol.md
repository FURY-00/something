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
- Shortcuts (use them, they avoid most API mistakes):
  - `cs.component("comp1")` get or create a component
  - `cs.material("Steel", density="7850[kg/m^3]", E="200e9[Pa]", nu=0.3, k="45[W/(m*K)]", cp="475[J/(kg*K)]")`
    keys: density, mu, k, cp, alpha, sigma, E, nu; `selection=[1, 2]` for particular domains
  - `cs.box("inlet", dim=1, xmin=-1e-6, xmax=1e-6, ymin=-1, ymax=1)` named selection by coordinates;
    then `feature.selection().named("inlet")`
  - `cs.operator("Maximum", "maxop1", selection="outlet", dim=1)` then `model.evaluate("maxop1(T)", "degC")`
  - `cs.study("Stationary")`, `cs.study("Transient", tlist="range(0,10,600)")`,
    `cs.study("Eigenfrequency", neigs=6)`, `cs.study("Frequency", plist="range(10,10,500)")`
  - `cs.sweep("std1", "L", "range(0.1,0.1,1)")` parametric sweep
  - `cs.plot("T", dim=2, path="~/Documents/Jarvis/Projects/comsol/T.png")` quick plot and PNG
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

## Recipe: eigenfrequencies of a cantilever (3D, vs beam theory)
```python
model = cs.new_model("cantilever_modes")
jm = model.java
jm.param().set("L", "0.3[m]"); jm.param().set("b", "0.02[m]"); jm.param().set("h", "0.005[m]")
comp = cs.component()
geom = comp.geom().create("geom1", 3)
blk = geom.create("blk1", "Block"); blk.set("size", ["L", "b", "h"]); geom.run()
cs.material("Steel", density="7850[kg/m^3]", E="200e9[Pa]", nu=0.3)
solid = comp.physics().create("solid", "SolidMechanics", "geom1")
cs.box("root", dim=2, xmin=-1e-6, xmax=1e-6, ymin=-1, ymax=1, zmin=-1, zmax=1)
solid.create("fix1", "Fixed", 2).selection().named("root")
comp.mesh().create("mesh1").autoMeshSize(4)
cs.study("Eigenfrequency", neigs=4)
model.solve("std1")
freqs = model.evaluate("solid.freq", "Hz")
import math
E, rho, L, h = 200e9, 7850, 0.3, 0.005
f1 = 1.875**2 / (2 * math.pi) * math.sqrt(E * h**2 / (12 * rho * L**4))
print("FEA frequencies (Hz):", np.round(np.atleast_1d(freqs), 1), f"| beam theory f1 = {f1:.1f} Hz")
cs.save()
```

## Recipe: parametric sweep (pressure drop vs pipe length)
Build a model with a parameter (e.g. `L`) used in the geometry, then:
```python
cs.study("Stationary")
cs.sweep("std1", "L", "range(0.1,0.1,0.5)")
model.solve("std1")
print("inlet pressure for each L:", model.evaluate("aveop1(p)", "Pa"))   # define aveop1 on the inlet first
```
Define the average operator before solving: `cs.operator("Average", "aveop1", selection="inlet", dim=1)`.

## Recipe: steady heat conduction with convection (2D block)
```python
model = cs.new_model("block_cooling")
jm = model.java
comp = cs.component()
geom = comp.geom().create("geom1", 2)
r = geom.create("r1", "Rectangle"); r.set("size", ["0.1", "0.02"]); geom.run()
cs.material("Aluminium", density="2700[kg/m^3]", k="200[W/(m*K)]", cp="900[J/(kg*K)]")
ht = comp.physics().create("ht", "HeatTransfer", "geom1")
cs.box("bottom", dim=1, xmin=-1e-6, xmax=0.1 + 1e-6, ymin=-1e-6, ymax=1e-6)
cs.box("top", dim=1, xmin=-1e-6, xmax=0.1 + 1e-6, ymin=0.02 - 1e-6, ymax=0.02 + 1e-6)
hot = ht.create("temp1", "TemperatureBoundary", 1); hot.selection().named("bottom"); hot.set("T0", "80[degC]")
conv = ht.create("hf1", "HeatFluxBoundary", 1); conv.selection().named("top")
print(cs.props(conv))                     # find the convective option names in this COMSOL version
conv.set("HeatFluxType", "ConvectiveHeatFlux"); conv.set("h", "25[W/(m^2*K)]"); conv.set("Text", "20[degC]")
comp.mesh().create("mesh1").autoMeshSize(5)
cs.operator("Minimum", "minop1", selection="top", dim=1)     # define operators before solving
cs.study("Stationary"); model.solve("std1")
print("coolest top temperature:", model.evaluate("minop1(T)", "degC"), "degC")
cs.plot("T", dim=2)
```

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

## GUI: parametric sweeps and optimisation
1. Right-click Study 1 > Parametric Sweep. Add a parameter from Global Definitions and a range (e.g. range(0.1,0.1,1)).
2. Compute. Results get one solution per value; plot a Global evaluation against the parameter with a 1D Plot Group.
3. Optimisation module: Study > Optimization, pick the objective (e.g. minimise max stress) and control variables.

## GUI: multiphysics coupling (e.g. thermal stress)
1. Add both physics (Heat Transfer in Solids and Solid Mechanics), or pick Structural Mechanics > Thermal Stress in the wizard.
2. Multiphysics node > Thermal Expansion couples them. Give the material a thermal expansion coefficient.
3. Solve a stationary study with both physics; plot von Mises stress and displacement.

## GUI: mesh convergence study
1. Solve with the default mesh, note the key result (max stress, pressure drop).
2. Mesh > Element Size > Finer, Extra fine; or add a Size node on critical boundaries. Recompute each time.
3. The mesh is good enough when the result changes by less than a few percent. Avoid judging stress at sharp corners.
