"""SolidWorks through its COM API (Windows only, SolidWorks must be installed).

Jarvis connects to the running SolidWorks (or starts it) and drives it the way
a VBA/C# macro would. The helpers here wrap the calls that are easy to get
wrong (argument lists of 20+ values, selection rules, metres vs millimetres),
so the code model can say ``sw.extrude(10)`` instead.

Sketch helpers take 2D millimetre coordinates in the active sketch's own
coordinate system (what SolidWorks' SketchManager expects). Selection helpers
for faces and edges take 3D model coordinates in millimetres.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import traceback

from . import RunResult, Skill

MM = 0.001

# swUserPreferenceStringValue_e
SW_DEFAULT_TEMPLATE_PART = 8
SW_DEFAULT_TEMPLATE_ASSEMBLY = 9
SW_DEFAULT_TEMPLATE_DRAWING = 10
# swEndConditions_e
BLIND, THROUGH_ALL, UP_TO_NEXT, MID_PLANE = 0, 1, 2, 6
PLANES = {"front": "Front Plane", "top": "Top Plane", "right": "Right Plane"}


class SolidWorksError(RuntimeError):
    pass


class SW:
    """Friendly wrappers around the SolidWorks API. Lengths in millimetres."""

    def __init__(self) -> None:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        self._win32 = win32com.client
        self.app = win32com.client.Dispatch("SldWorks.Application")
        self.app.Visible = True
        # SelectByID2 needs a real "nothing" COM object for its Callout argument.
        self.NOTHING = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

    # -- documents -----------------------------------------------------------
    @property
    def model(self):
        doc = self.app.ActiveDoc
        if doc is None:
            raise SolidWorksError("No document is open. Call sw.new_part() first.")
        return doc

    def new_part(self):
        template = self.app.GetUserPreferenceStringValue(SW_DEFAULT_TEMPLATE_PART)
        doc = self.app.NewDocument(template, 0, 0, 0)
        if doc is None:
            raise SolidWorksError(f"Couldn't create a part from template {template!r}")
        print(f"New part: {doc.GetTitle()}")
        return doc

    def new_assembly(self):
        template = self.app.GetUserPreferenceStringValue(SW_DEFAULT_TEMPLATE_ASSEMBLY)
        return self.app.NewDocument(template, 0, 0, 0)

    def open(self, path: str):
        """Open a part (.sldprt), assembly (.sldasm) or drawing (.slddrw)."""
        kind = {"sldprt": 1, "sldasm": 2, "slddrw": 3}[path.lower().rsplit(".", 1)[-1]]
        errors = self._win32.VARIANT(16387, 0)  # VT_BYREF | VT_I4
        warnings = self._win32.VARIANT(16387, 0)
        doc = self.app.OpenDoc6(path, kind, 1, "", errors, warnings)  # 1 = silent
        if doc is None:
            raise SolidWorksError(f"Couldn't open {path} (error {errors.value})")
        return doc

    def save(self, path: str) -> str:
        """Save (or export by extension: .sldprt .step .stp .stl .igs .x_t .pdf)."""
        code = self.model.SaveAs3(path, 0, 1)  # 1 = silent
        if code != 0:
            raise SolidWorksError(f"Save failed with code {code} for {path}")
        print(f"Saved: {path}")
        return path

    # -- selection -----------------------------------------------------------
    def select(self, name: str, kind: str, x=0.0, y=0.0, z=0.0, append=False, mark=0) -> bool:
        """Select by name and type ('PLANE', 'SKETCH', 'BODYFEATURE', 'EDGE', 'FACE', 'AXIS').

        For faces/edges pass name='' and a point ON the entity, in millimetres (model coordinates).
        """
        ok = self.model.Extension.SelectByID2(name, kind, x * MM, y * MM, z * MM, append, mark,
                                              self.NOTHING, 0)
        if not ok:
            raise SolidWorksError(f"Couldn't select {kind} {name!r} at ({x}, {y}, {z}) mm")
        return ok

    def clear_selection(self) -> None:
        self.model.ClearSelection2(True)

    # -- sketching -----------------------------------------------------------
    def start_sketch(self, plane: str = "front", face_point=None):
        """Start a sketch on 'front'/'top'/'right', a named plane, or a face at face_point (mm)."""
        self.clear_selection()
        if face_point is not None:
            self.select("", "FACE", *face_point)
        else:
            self.select(PLANES.get(plane.lower(), plane), "PLANE")
        self.model.SketchManager.InsertSketch(True)
        self.model.SketchManager.AddToDB = True  # place points exactly, no snapping
        return self.model.SketchManager

    def finish_sketch(self) -> str:
        sm = self.model.SketchManager
        sm.AddToDB = False
        sm.InsertSketch(True)  # toggles the sketch closed
        name = self.last_feature().Name
        print(f"Sketch finished: {name}")
        return name

    def _check(self, entity, what):
        if entity is None:
            raise SolidWorksError(f"SolidWorks couldn't create the {what}")
        return entity

    def line(self, x1, y1, x2, y2):
        return self._check(self.model.SketchManager.CreateLine(x1 * MM, y1 * MM, 0, x2 * MM, y2 * MM, 0), "line")

    def polyline(self, points, close=True):
        pts = list(points) + ([points[0]] if close else [])
        return [self.line(*a, *b) for a, b in zip(pts, pts[1:])]

    def centerline(self, x1, y1, x2, y2):
        return self._check(self.model.SketchManager.CreateCenterLine(x1 * MM, y1 * MM, 0, x2 * MM, y2 * MM, 0),
                           "centerline")

    def circle(self, xc, yc, radius):
        return self._check(self.model.SketchManager.CreateCircleByRadius(xc * MM, yc * MM, 0, radius * MM), "circle")

    def rectangle(self, x1, y1, x2, y2):
        """Corner rectangle from (x1, y1) to (x2, y2)."""
        return self._check(self.model.SketchManager.CreateCornerRectangle(x1 * MM, y1 * MM, 0, x2 * MM, y2 * MM, 0),
                           "rectangle")

    def center_rectangle(self, xc, yc, width, height):
        return self._check(self.model.SketchManager.CreateCenterRectangle(
            xc * MM, yc * MM, 0, (xc + width / 2) * MM, (yc + height / 2) * MM, 0), "rectangle")

    def arc(self, xc, yc, x1, y1, x2, y2, clockwise=False):
        """Centre-point arc from (x1, y1) to (x2, y2) around (xc, yc)."""
        direction = -1 if clockwise else 1
        return self._check(self.model.SketchManager.CreateArc(
            xc * MM, yc * MM, 0, x1 * MM, y1 * MM, 0, x2 * MM, y2 * MM, 0, direction), "arc")

    def polygon(self, xc, yc, radius, sides=6, inscribed=True):
        return self._check(self.model.SketchManager.CreatePolygon(
            xc * MM, yc * MM, 0, (xc + radius) * MM, yc * MM, 0, sides, inscribed), "polygon")

    def slot(self, x1, y1, x2, y2, width):
        """Straight slot between two centre points."""
        return self._check(self.model.SketchManager.CreateSketchSlot(
            0, 0, width * MM, x1 * MM, y1 * MM, 0, x2 * MM, y2 * MM, 0, 0, 0, 0, 1, False), "slot")

    def point(self, x, y):
        return self._check(self.model.SketchManager.CreatePoint(x * MM, y * MM, 0), "point")

    def dimension(self, x, y):
        """Add a smart dimension to the selected sketch entity, text placed at (x, y) mm."""
        return self.model.AddDimension2(x * MM, y * MM, 0)

    # -- features ------------------------------------------------------------
    def last_feature(self):
        return self.model.FeatureByPositionReverse(0)

    def _select_last_sketch(self, sketch=None):
        self.clear_selection()
        if sketch:
            self.select(sketch, "SKETCH")
        else:
            feat = self.last_feature()
            if not feat.Select2(False, 0):
                raise SolidWorksError(f"Couldn't select sketch {feat.Name}")

    def extrude(self, depth, reverse=False, mid_plane=False, through_all=False, sketch=None, merge=True):
        """Boss-extrude the last (or named) sketch by depth mm."""
        self._select_last_sketch(sketch)
        end = THROUGH_ALL if through_all else MID_PLANE if mid_plane else BLIND
        fm = self.model.FeatureManager
        feat = fm.FeatureExtrusion2(
            True, False, reverse, end, 0, depth * MM, 0.0, False, False, False, False,
            0.0, 0.0, False, False, False, False, merge, True, True, 0, 0.0, False)
        feat = self._check(feat, "extrusion (is the sketch closed?)")
        print(f"Extruded {feat.Name}: {depth} mm")
        return feat

    def cut(self, depth=None, reverse=False, through_all=False, sketch=None):
        """Extruded cut of the last (or named) sketch: depth mm, or through_all=True."""
        self._select_last_sketch(sketch)
        end = THROUGH_ALL if through_all or depth is None else BLIND
        fm = self.model.FeatureManager
        d = (depth or 0.01) * MM
        feat = fm.FeatureCut4(
            True, False, reverse, end, 0, d, 0.0, False, False, False, False, 0.0, 0.0,
            False, False, False, False, False, True, True, True, True, False, 0, 0.0, False, False)
        feat = self._check(feat, "cut (does the sketch overlap the part?)")
        print(f"Cut {feat.Name}")
        return feat

    def revolve(self, angle=360, sketch=None, cut=False):
        """Revolve the last sketch around its centerline (draw one with sw.centerline)."""
        import math

        self._select_last_sketch(sketch)
        fm = self.model.FeatureManager
        feat = fm.FeatureRevolve2(True, True, False, cut, False, False, 0, 0, math.radians(angle), 0.0,
                                  False, False, 0.0, 0.0, 0, 0.0, 0.0, True, True, True)
        feat = self._check(feat, "revolve (does the sketch have a centerline and no crossing?)")
        print(f"Revolved {feat.Name}: {angle} degrees")
        return feat

    def fillet(self, radius, edge_points):
        """Round edges. edge_points: list of (x, y, z) mm points lying ON each edge."""
        self.clear_selection()
        for i, p in enumerate(edge_points):
            self.select("", "EDGE", *p, append=i > 0, mark=1)
        fm = self.model.FeatureManager
        try:
            feat = fm.FeatureFillet3(195, radius * MM, 0.0, 0.0, 0, 0, 0,
                                     None, None, None, None, None, None, None)
        except Exception:  # noqa: BLE001 - signature differs between versions
            feat = None
        if feat is None:  # the older, simpler call still works in current versions
            feat = self.model.FeatureFillet(195, radius * MM, 0, 0, None, None, None)
        feat = self._check(feat, "fillet (are the edge points exactly on edges?)")
        print(f"Filleted {len(edge_points)} edge(s) R{radius} mm")
        return feat

    def chamfer(self, distance, edge_points, angle=45):
        import math

        self.clear_selection()
        for i, p in enumerate(edge_points):
            self.select("", "EDGE", *p, append=i > 0)
        feat = self.model.FeatureManager.InsertFeatureChamfer(4, 1, distance * MM, math.radians(angle),
                                                               0, 0, 0, 0)
        return self._check(feat, "chamfer")

    def shell(self, thickness, face_point):
        """Hollow the part, removing the face at face_point (mm)."""
        self.clear_selection()
        self.select("", "FACE", *face_point, mark=1)
        self.model.InsertFeatureShell(thickness * MM, False)
        print(f"Shelled to {thickness} mm")
        return self.last_feature()

    def plane_offset(self, base="front", distance=10):
        """New reference plane parallel to base at distance mm."""
        self.clear_selection()
        self.select(PLANES.get(base.lower(), base), "PLANE", mark=0)
        feat = self.model.FeatureManager.InsertRefPlane(8, distance * MM, 0, 0, 0, 0)  # 8 = distance
        feat = self._check(feat, "reference plane")
        print(f"Plane {feat.Name}: {distance} mm from {base}")
        return feat.Name

    def set_material(self, name="Plain Carbon Steel", database="SOLIDWORKS Materials"):
        config = self.model.ConfigurationManager.ActiveConfiguration.Name
        self.model.SetMaterialPropertyName2(config, database, name)
        print(f"Material: {name}")

    # -- holes and patterns (sketch-based: more reliable than pattern features) --
    def holes(self, face_point, centres, diameter, depth=None):
        """Cut round holes at 2D sketch positions [(x, y), ...] on the face at face_point (mm)."""
        self.start_sketch(face_point=face_point)
        for x, y in centres:
            self.circle(x, y, diameter / 2)
        self.finish_sketch()
        feat = self.cut(depth=depth, through_all=depth is None)
        print(f"{len(centres)} hole(s) of {diameter} mm")
        return feat

    def bolt_circle(self, face_point, pcd, count, diameter, start_angle=0.0, centre=(0, 0), depth=None):
        """Holes evenly spaced on a pitch circle diameter `pcd` (mm), angles in degrees."""
        import math

        cx, cy = centre
        pts = [(cx + pcd / 2 * math.cos(math.radians(start_angle + 360 * i / count)),
                cy + pcd / 2 * math.sin(math.radians(start_angle + 360 * i / count))) for i in range(count)]
        return self.holes(face_point, pts, diameter, depth)

    def hole_grid(self, face_point, x0, y0, nx, ny, dx, dy, diameter, depth=None):
        """A rectangular grid of holes starting at (x0, y0) with pitches dx, dy (mm)."""
        pts = [(x0 + i * dx, y0 + j * dy) for i in range(nx) for j in range(ny)]
        return self.holes(face_point, pts, diameter, depth)

    # -- drawings, assemblies, parameters -------------------------------------
    def drawing(self, part_path: str, pdf_path: str | None = None):
        """Standard three-view drawing of a saved part; optionally save it as PDF."""
        template = self.app.GetUserPreferenceStringValue(SW_DEFAULT_TEMPLATE_DRAWING)
        drw = self.app.NewDocument(template, 12, 0.42, 0.297)  # A3 landscape
        if drw is None:
            raise SolidWorksError("Couldn't create a drawing (check the default drawing template)")
        if not drw.Create3rdAngleViews2(part_path):
            raise SolidWorksError(f"Couldn't create views of {part_path} (is it saved?)")
        if pdf_path:
            self.save(pdf_path)
        print(f"Drawing created for {part_path}")
        return drw

    def insert_component(self, path: str, x=0.0, y=0.0, z=0.0):
        """Add a saved part or assembly into the active assembly at (x, y, z) mm."""
        comp = self.model.AddComponent5(path, 0, "", False, "", x * MM, y * MM, z * MM)
        comp = self._check(comp, f"component from {path} (is an assembly active?)")
        print(f"Inserted {comp.Name2}")
        return comp

    MATES = {"coincident": 0, "concentric": 1, "perpendicular": 2, "parallel": 3, "tangent": 4,
             "distance": 5, "angle": 6}

    def mate(self, kind: str, distance=0.0, angle=0.0, flip=False):
        """Mate the two currently selected entities (select them with sw.select(..., append=True))."""
        import math

        err = self._win32.VARIANT(16387, 0)
        mate = self.model.AddMate5(self.MATES[kind], 0 if not flip else 1, flip, distance * MM,
                                   distance * MM, distance * MM, 1, 1, math.radians(angle),
                                   math.radians(angle), math.radians(angle), False, False, 0, err)
        mate = self._check(mate, f"{kind} mate (error {getattr(err, 'value', '?')})")
        self.rebuild()
        print(f"Added {kind} mate")
        return mate

    def equation(self, text: str) -> None:
        """Add an equation, e.g. '"D1@Sketch1" = 2 * "D2@Sketch1"' or '"thickness" = 8'."""
        self.model.GetEquationMgr().Add2(-1, text, True)
        self.rebuild()
        print(f"Equation: {text}")

    def set_property(self, name: str, value: str) -> None:
        """Custom file property (part number, description, author...)."""
        self.model.Extension.CustomPropertyManager("").Add3(name, 30, str(value), 2)
        print(f"Property {name} = {value}")

    # -- information ---------------------------------------------------------
    def mass_properties(self) -> dict:
        mp = self.model.Extension.CreateMassProperty()
        info = {"mass_kg": mp.Mass, "volume_mm3": mp.Volume * 1e9, "area_mm2": mp.SurfaceArea * 1e6}
        print(f"Mass {info['mass_kg']:.4f} kg, volume {info['volume_mm3']:.1f} mm^3, "
              f"area {info['area_mm2']:.1f} mm^2")
        return info

    def features(self) -> list[str]:
        names = []
        feat = self.model.FirstFeature()
        while feat is not None:
            names.append(f"{feat.Name} ({feat.GetTypeName2()})")
            feat = feat.GetNextFeature()
        return names

    def dimensions(self) -> dict:
        """Every dimension in the model: {"D1@Sketch1": value} (mm, or radians for angles)."""
        out = {}
        feat = self.model.FirstFeature()
        while feat is not None:
            disp = feat.GetFirstDisplayDimension()
            while disp is not None:
                dim = disp.GetDimension2(0)
                value = dim.SystemValue
                out[dim.FullName] = value if dim.GetType() == 2 else round(value / MM, 6)  # 2 = angular
                disp = feat.GetNextDisplayDimension(disp)
            feat = feat.GetNextFeature()
        return out

    def set_dimension(self, full_name: str, value: float) -> None:
        """Change a dimension, e.g. set_dimension("D1@Boss-Extrude1", 25) (mm; radians for angles)."""
        dim = self.model.Parameter(full_name)
        if dim is None:
            raise SolidWorksError(f"No dimension {full_name!r}. Known: {list(self.dimensions())}")
        dim.SystemValue = value if dim.GetType() == 2 else value * MM
        self.rebuild()
        print(f"{full_name} = {value}")

    def rebuild(self) -> None:
        self.model.EditRebuild3()

    def zoom(self, view="isometric") -> None:
        views = {"isometric": "*Isometric", "front": "*Front", "top": "*Top", "right": "*Right",
                 "trimetric": "*Trimetric"}
        self.model.ShowNamedView2(views.get(view, view), -1)
        self.model.ViewZoomtofit2()

    def undo(self, steps=1) -> None:
        self.model.EditUndo2(steps)


class SolidWorksSkill(Skill):
    name = "solidworks"
    title = "SolidWorks"
    where = ("in Python on the user's PC, connected to SolidWorks over COM. Available: `sw` "
             "(helpers, lengths in mm), `swApp` (ISldWorks), `MM` (=0.001, mm to metres), and "
             "`win32com`")
    units = "millimetres in sw helpers; metres in the raw API (multiply mm by MM)"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._namespace: dict | None = None

    def detect(self) -> str | None:
        if not sys.platform.startswith("win"):
            return "SolidWorks only runs on Windows"
        try:
            import winreg

            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "SldWorks.Application"))
        except OSError:
            return "SolidWorks isn't installed"
        if importlib.util.find_spec("win32com") is None:
            return "pywin32 is missing (pip install pywin32)"
        return None

    def _session(self) -> dict:
        sw = SW()  # reconnect each time: COM objects belong to the thread that made them
        if self._namespace is None:
            self._namespace = {"__name__": "__jarvis__"}
        import win32com

        self._namespace.update(sw=sw, swApp=sw.app, MM=MM, win32com=win32com)
        return self._namespace

    def run(self, code: str) -> RunResult:
        buf = io.StringIO()
        try:
            ns = self._session()
            with contextlib.redirect_stdout(buf):
                exec(compile(code, "<jarvis>", "exec"), ns)
            return RunResult(True, buf.getvalue())
        except Exception:
            return RunResult(False, buf.getvalue(), traceback.format_exc(limit=6))

    def state(self) -> str:
        result = self.run(
            "doc = swApp.ActiveDoc\n"
            "if doc is None:\n    print('No document open.')\n"
            "else:\n"
            "    print('Active document:', doc.GetTitle(), '| type', doc.GetType(), '| path', doc.GetPathName() or '(unsaved)')\n"
            "    print('Features:', ', '.join(sw.features()))\n"
        )
        return result.output if result.ok else f"(couldn't read SolidWorks: {result.error.splitlines()[-1]})"
