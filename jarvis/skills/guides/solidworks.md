# SolidWorks automation guide

Scripts run in Python on the user's Windows PC, connected to SolidWorks through its COM
API. Pre-loaded: `sw` (helpers below, **millimetres**), `swApp` (the SldWorks application),
`MM = 0.001` (multiply mm by MM for raw API calls, which use **metres** and **radians**),
`win32com`. Work in the active document unless the task says to start a new part.

## Helpers (pre-loaded as `sw`, prefer these)
Documents: `sw.new_part()`, `sw.new_assembly()`, `sw.open(path)`, `sw.save(path)` (extension picks the
format: .sldprt .step .stp .stl .igs .x_t .pdf), `sw.model` (active ModelDoc2)
Sketching (2D coordinates in the sketch plane, mm):
- `sw.start_sketch('front'|'top'|'right'|plane_name)` or `sw.start_sketch(face_point=(x, y, z))` to sketch on a face
- `sw.line(x1, y1, x2, y2)`, `sw.polyline([(x, y), ...], close=True)`, `sw.centerline(x1, y1, x2, y2)`
- `sw.circle(xc, yc, r)`, `sw.rectangle(x1, y1, x2, y2)`, `sw.center_rectangle(xc, yc, w, h)`
- `sw.arc(xc, yc, x1, y1, x2, y2, clockwise=False)`, `sw.polygon(xc, yc, r, sides=6)`, `sw.slot(x1, y1, x2, y2, width)`, `sw.point(x, y)`
- `sw.finish_sketch()` returns the sketch name
Features (act on the last sketch unless `sketch=` is given):
- `sw.extrude(depth, reverse=False, mid_plane=False, through_all=False)` boss
- `sw.cut(depth=None, reverse=False, through_all=False)` extruded cut (depth None = through all)
- `sw.revolve(angle=360, cut=False)` needs a centerline in the sketch as the axis
- `sw.fillet(r, [edge points])`, `sw.chamfer(d, [edge points], angle=45)`, `sw.shell(t, face_point)`
- `sw.plane_offset('front', 25)` new plane, returns its name for `start_sketch`
- `sw.set_material('AISI 304')`, `sw.mass_properties()`, `sw.features()`, `sw.dimensions()`,
  `sw.set_dimension('D1@Boss-Extrude1', 25)`, `sw.rebuild()`, `sw.zoom('isometric')`, `sw.undo()`
- `sw.select(name, kind, x, y, z, append=False)` kinds: PLANE, SKETCH, BODYFEATURE, FACE, EDGE, AXIS, EXTSKETCHSEGMENT

## Rules that avoid most failures
- Always `sw.finish_sketch()` before a feature. Profiles for extrude/revolve must be closed loops that don't cross.
- Sketch on standard planes: Front = XY (x right, y up), Top = XZ (sketch y is model -Z), Right = YZ.
- Faces and edges are picked by a 3D point ON them, in model mm. For a block extruded from the
  Front Plane by depth d, the front face is at z = d, the back at z = 0. Pick edge points at an
  edge's midpoint, not a corner.
- To make several holes, draw all circles in ONE sketch and cut once. This is more reliable
  than pattern features. Use math for positions (bolt circle: x = R cos(a), y = R sin(a)).
- To change an existing part, look up names with `sw.dimensions()` and use `sw.set_dimension`.
- After finishing, call `sw.zoom('isometric')` and print what was made (sizes, mass, file).
- Raw calls that return None usually mean "selection was wrong" or "invalid geometry".

## Raw API essentials (when helpers don't cover it)
- `m = sw.model`; sketch manager `m.SketchManager`; feature manager `m.FeatureManager`; extension `m.Extension`
- Sketch fillet: select a sketch corner point or two lines, `m.SketchManager.CreateFillet(r*MM, 1)`
- Sketch relations: select entities (`sw.select('Line1', 'SKETCHSEGMENT', append=...)`), then
  `m.SketchAddConstraints('sgHORIZONTAL2D'|'sgVERTICAL2D'|'sgCOINCIDENT'|'sgTANGENT'|'sgPARALLEL'|'sgPERPENDICULAR'|'sgEQUAL'|'sgCONCENTRIC'|'sgFIXED')`
- Dimensions: select an entity, `m.AddDimension2(x*MM, y*MM, 0)`; change by name: `m.Parameter('D1@Sketch1').SystemValue = 0.05`
- Offset entities: select sketch entities, `m.SketchManager.SketchOffset2(d*MM, False, True, 0, 0, True)`
- Mirror sketch entities: select entities plus a centerline (append), `m.SketchMirror()`
- Spline: `m.SketchManager.CreateSpline2(points_flat_list_in_metres, True)` with [x1, y1, 0, x2, y2, 0, ...]
- Equations: `m.GetEquationMgr().Add2(-1, '"D1@Sketch1" = 2 * "D2@Sketch1"', True)`
- Custom properties: `m.Extension.CustomPropertyManager('').Add3('PartNo', 30, 'P-001', 2)` (30 = text)
- Mirror a feature: select the feature (append) and a plane (mark 2), `m.FeatureManager.InsertMirrorFeature2(False, False, False, False, 0)`
- Sweep: profile sketch + path sketch; loft: two or more profile sketches on offset planes (`plane_offset`).
  These have long argument lists that differ between versions. If one fails, read the error, or build
  the shape another way (revolve, stacked extrudes).
- Assemblies: `asm = sw.new_assembly()`, then `asm.AddComponent5(part_path, 0, '', False, '', x, y, z)` (metres).
  Mates: select two faces (append), then `asm.AddMate5(type, align, flip, dist, 0, 0, 0, 0, 0, 0, 0, False, False, 0, err)`
  where type 0 = coincident, 1 = concentric, 2 = perpendicular, 3 = parallel, 5 = distance.
- Drawings: `swApp.NewDocument(swApp.GetUserPreferenceStringValue(10), 12, 0.42, 0.297)` (A3), then
  `drw.CreateDrawViewFromModelView3(part_path, '*Front', x, y, 0)` for each view.
- Measure: `m.Extension.CreateMeasure()`; mass: `sw.mass_properties()`
- Units in the document: `m.GetUserPreferenceIntegerValue(...)` (the helpers always use mm, whatever the document shows)

## Recipe: rectangular plate with four corner holes
```python
sw.new_part()
sw.start_sketch("front")
sw.center_rectangle(0, 0, 100, 60)
sw.finish_sketch()
sw.extrude(8)
sw.start_sketch(face_point=(0, 0, 8))          # top face of the plate (z = thickness)
for x in (-40, 40):
    for y in (-20, 20):
        sw.circle(x, y, 3)                       # M6 clearance, 6 mm holes
sw.finish_sketch()
sw.cut(through_all=True)
sw.fillet(5, [(50, 30, 4), (-50, 30, 4), (50, -30, 4), (-50, -30, 4)])  # vertical corner edges
sw.set_material("Plain Carbon Steel"); sw.mass_properties(); sw.zoom()
```

## Recipe: flange / round part by revolving a profile
```python
sw.new_part()
sw.start_sketch("front")
sw.centerline(0, -10, 0, 60)                     # axis of revolution (vertical)
sw.polyline([(10, 0), (50, 0), (50, 10), (20, 10), (20, 40), (10, 40)])  # half cross-section, x = radius
sw.finish_sketch()
sw.revolve(360)
```

## Recipe: L-bracket
```python
sw.new_part()
sw.start_sketch("front")
sw.polyline([(0, 0), (60, 0), (60, 6), (6, 6), (6, 40), (0, 40)])  # L profile, 6 mm thick
sw.finish_sketch()
sw.extrude(30)
```

## Recipe: bolt circle (holes on a pitch circle)
```python
import math
sw.start_sketch(face_point=(0, 0, thickness))
for i in range(6):
    a = 2 * math.pi * i / 6
    sw.circle(40 * math.cos(a), 40 * math.sin(a), 4)
sw.finish_sketch(); sw.cut(through_all=True)
```

## Recipe: hollow box (shell)
Extrude a closed rectangle, then `sw.shell(2, face_point=(0, 0, height))` to remove the top face
and leave 2 mm walls.

## Recipe: just sketch a shape from geometry the user describes
Compute the vertices with math, then draw them. For example, an equilateral triangle with 50 mm
sides: `h = 50 * math.sqrt(3) / 2; sw.polyline([(0, 0), (50, 0), (25, h)])`. A regular hexagon
across flats 20: `sw.polygon(0, 0, 10 / math.cos(math.pi / 6), 6)`. Leave the sketch open if the
user only asked for a sketch: call `sw.finish_sketch()` only when they want a feature next.

## GUI: sketch tools (line, circle, rectangle, arc)
1. Click the Sketch tab, then Sketch, and pick a plane (Front, Top or Right) or a flat face.
2. Line: click Line (or press L if mapped), click the start point, click the end point, Esc to stop.
3. Circle: Circle tool, click the centre, drag out the radius. Rectangle: Corner Rectangle, click two corners.
4. Arcs: Centerpoint Arc (centre, start, end) or Tangent Arc from the end of a line.
5. Smart Dimension (D): click an entity, place the dimension, type the value. Black geometry = fully defined.
6. Relations: select entities, then pick Horizontal, Vertical, Coincident, Tangent, Equal... in the PropertyManager.
7. Exit Sketch (top-right corner icon) when done.

## GUI: extruded boss and cut
1. Select or finish a closed sketch. Features tab > Extruded Boss/Base.
2. Set Direction 1 (Blind, Through All, Mid Plane, Up To Surface) and the depth. Tick Merge result.
3. Extruded Cut works the same way on a sketch drawn on a face of the part.

## GUI: revolve
1. Sketch a half profile and a Centerline on the same sketch (the axis).
2. Features > Revolved Boss/Base; pick the centerline as the axis if asked; set the angle (360).

## GUI: fillet and chamfer
1. Features > Fillet. Choose Constant Size. Click the edges (or a face for all its edges). Enter the radius.
2. Chamfer is under the Fillet dropdown: Distance-Angle or Distance-Distance.

## GUI: hole wizard
1. Features > Hole Wizard. Pick the type (Counterbore, Countersink, Hole, Tap), standard (ISO/ANSI) and size.
2. Positions tab: click the face, then click to place each hole centre; dimension them with Smart Dimension.

## GUI: patterns and mirror
1. Linear Pattern: pick an edge for direction, spacing and count, and the features to pattern.
2. Circular Pattern: pick an axis (View > Temporary Axes shows hole axes), angle and count.
3. Mirror: pick the mirror face or plane and the features or bodies to mirror.

## GUI: shell, rib, draft, reference planes
1. Shell: pick the faces to remove and the thickness. 2. Rib: sketch an open line, Features > Rib, set thickness.
3. Draft: neutral plane plus faces and angle. 4. Reference Geometry > Plane: pick a plane and set the offset distance.

## GUI: sweep and loft
1. Sweep needs a closed profile sketch and a path sketch that starts on the profile's plane.
   Features > Swept Boss/Base, pick the profile and the path.
2. Loft needs two or more profiles on different planes. Features > Lofted Boss/Base, pick them in order.

## GUI: materials, mass and export
1. Right-click Material in the FeatureManager tree > Edit Material, pick one, then Apply.
2. Evaluate tab > Mass Properties shows mass, volume and centre of mass.
3. File > Save As, choose STEP, STL, IGES, Parasolid or PDF for exports.

## GUI: assemblies and mates
1. File > New > Assembly, Insert Components, browse to the parts. The first part is fixed at the origin.
2. Mate: select two faces or edges, choose Coincident, Concentric, Parallel, Distance, Angle... and OK.
3. Move Component to test the motion that remains.

## GUI: drawings
1. File > Make Drawing from Part, pick the sheet size, then drag the Front, Top and Right views onto the sheet.
2. Annotation tab > Model Items imports the dimensions. Add a Title Block and Save As PDF.

## GUI: SolidWorks Simulation (static stress)
1. Tools > Add-ins, tick SOLIDWORKS Simulation. Simulation tab > New Study > Static.
2. Apply Material, Fixtures (Fixed Geometry on the mounting faces) and External Loads (Force/Pressure).
3. Mesh > Create Mesh, then Run. Check von Mises stress, displacement and factor of safety plots.
