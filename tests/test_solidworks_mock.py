"""SolidWorks helpers and guide recipes against a stand-in for the COM API.

The stand-in encodes the documented argument counts of the API calls the
helpers use. It can't prove SolidWorks behaves the same way (only a real
SolidWorks can), but it catches Python mistakes in helpers and recipes.
"""

import re
import sys
import types

import pytest

from jarvis.config import load_config
from jarvis.skills.guides import load_guide

ARG_COUNTS = {"FeatureExtrusion2": 23, "FeatureCut4": 27, "FeatureRevolve2": 20, "FeatureFillet3": 14,
              "SelectByID2": 9, "CreateLine": 6, "CreateCircleByRadius": 4, "CreateCenterRectangle": 6,
              "CreateCornerRectangle": 6, "CreateCenterLine": 6, "CreatePolygon": 8, "SaveAs3": 3,
              "InsertRefPlane": 6, "SetMaterialPropertyName2": 3}


class Feature:
    def __init__(self, name, kind):
        self.Name, self.kind, self.next = name, kind, None

    def Select2(self, append, mark):
        return True

    def GetTypeName2(self):
        return self.kind

    def GetNextFeature(self):
        return self.next

    def GetFirstDisplayDimension(self):
        return None


class Recorder:
    def __init__(self, doc):
        self.doc = doc

    def __getattr__(self, name):
        def call(*args):
            if name in ARG_COUNTS:
                assert len(args) == ARG_COUNTS[name], f"{name} got {len(args)} args"
            self.doc.calls.append((name, args))
            if name.startswith("Feature") or name == "InsertRefPlane":
                kind = {"FeatureExtrusion2": "Extrusion", "FeatureCut4": "Cut",
                        "FeatureRevolve2": "Revolution"}.get(name, name)
                return self.doc.add_feature(kind)
            if name == "InsertSketch" and self.doc.in_sketch:
                self.doc.add_feature("ProfileFeature", "Sketch")
            if name == "InsertSketch":
                self.doc.in_sketch = not self.doc.in_sketch
            if name == "CreateMassProperty":
                return types.SimpleNamespace(Mass=0.4, Volume=5e-5, SurfaceArea=0.02)
            return 0 if name == "SaveAs3" else object()
        return call


class Doc:
    def __init__(self):
        self.calls, self.features, self.in_sketch = [], [], False
        self.SketchManager = Recorder(self)
        self.FeatureManager = Recorder(self)
        self.Extension = Recorder(self)
        self.ConfigurationManager = types.SimpleNamespace(ActiveConfiguration=types.SimpleNamespace(Name="Default"))

    def add_feature(self, kind, prefix=None):
        n = sum(1 for f in self.features if f.kind == kind) + 1
        feat = Feature(f"{prefix or kind}{n}", kind)
        if self.features:
            self.features[-1].next = feat
        self.features.append(feat)
        return feat

    def FeatureByPositionReverse(self, i):
        return self.features[-1 - i]

    def FirstFeature(self):
        return self.features[0] if self.features else None

    def GetTitle(self):
        return "Part1"

    def __getattr__(self, name):
        return Recorder(self).__getattr__(name)


class App:
    def __init__(self):
        self.ActiveDoc = None
        self.Visible = False

    def GetUserPreferenceStringValue(self, which):
        return "C:/templates/Part.prtdot"

    def NewDocument(self, template, *args):
        self.ActiveDoc = Doc()
        return self.ActiveDoc


@pytest.fixture
def skill(monkeypatch, tmp_path):
    app = App()
    win32com = types.ModuleType("win32com")
    client = types.ModuleType("win32com.client")
    client.Dispatch = lambda progid: app
    client.VARIANT = lambda vt, value: types.SimpleNamespace(vt=vt, value=value)
    win32com.client = client
    pythoncom = types.SimpleNamespace(CoInitialize=lambda: None, VT_DISPATCH=9)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    from jarvis.skills.solidworks import SolidWorksSkill

    s = SolidWorksSkill(load_config())
    s.app = app
    return s


def test_helpers_convert_mm_and_pass_the_right_arguments(skill):
    result = skill.run("sw.new_part()\nsw.start_sketch('front')\nsw.center_rectangle(0, 0, 100, 60)\n"
                       "sw.finish_sketch()\nsw.extrude(8)\nsw.set_material('AISI 304')\nsw.mass_properties()")
    assert result.ok, result.error
    calls = skill.app.ActiveDoc.calls
    rect = next(args for name, args in calls if name == "CreateCenterRectangle")
    assert rect == (0, 0, 0, 0.05, 0.03, 0)  # millimetres became metres
    extrude = next(args for name, args in calls if name == "FeatureExtrusion2")
    assert extrude[5] == pytest.approx(0.008)
    assert ("SetMaterialPropertyName2", ("Default", "SOLIDWORKS Materials", "AISI 304")) in calls
    assert "Mass 0.4000 kg" in result.output
    assert "Sketch1" in result.output and "Extrusion1" in result.output


def test_every_solidworks_recipe_runs_against_the_api_shape(skill):
    _, sections = load_guide("solidworks")
    blocks = [(s.heading, b) for s in sections for b in re.findall(r"```python\n(.*?)```", s.body, flags=re.S)]
    assert len(blocks) >= 4
    for heading, block in blocks:
        setup = "sw.new_part()\nthickness = 8\n" if "thickness" in block and "new_part" not in block else ""
        result = skill.run(setup + block)
        assert result.ok, f"{heading}:\n{result.error}"


def test_state_lists_the_feature_tree(skill):
    skill.run("sw.new_part()\nsw.start_sketch('top')\nsw.circle(0, 0, 10)\nsw.finish_sketch()\nsw.extrude(5)")
    state = skill.state()
    assert "Active document: Part1" in state and "Sketch1 (ProfileFeature)" in state
