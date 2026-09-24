"""COMSOL and Ansys helpers and guide recipes against permissive stand-ins.

Only a real COMSOL/Ansys can check the physics API calls themselves; these
tests make sure the helpers and the guide's recipes are sound Python that
flows the way Jarvis expects (sessions, current model, results, saving).
"""

import re
import sys
import types
from unittest import mock

import numpy as np
import pytest

from jarvis.config import load_config
from jarvis.skills.guides import load_guide


def recipes(name):
    """Standalone examples (reference snippets in other sections assume an open model)."""
    _, sections = load_guide(name)
    return [(s.heading, b) for s in sections if s.kind == "recipe"
            for b in re.findall(r"```python\n(.*?)```", s.body, flags=re.S)]


@pytest.fixture
def comsol(monkeypatch, tmp_path):
    def make_model(name):
        m = mock.MagicMock(name=f"model:{name}")
        m.name.return_value = name
        m.file.return_value = None
        m.parameters.return_value = {"L": "10[m]"}
        m.evaluate.return_value = np.array([0.02, 0.1, 0.098])
        return m

    client = mock.MagicMock()
    client.create.side_effect = make_model
    fake_mph = types.ModuleType("mph")
    fake_mph.start = mock.MagicMock(return_value=client)
    fake_mph.discovery = types.SimpleNamespace(backend=lambda version=None: {"name": "6.2"})
    monkeypatch.setitem(sys.modules, "mph", fake_mph)
    from jarvis.skills.comsol import ComsolSkill

    cfg = load_config()
    cfg.paths.projects = tmp_path
    skill = ComsolSkill(cfg)
    skill.fake_start = fake_mph.start
    return skill


def test_comsol_session_and_current_model(comsol):
    assert comsol.detect() is None
    assert "No COMSOL model open" in comsol.state()
    r = comsol.run("model = cs.new_model('beam')\njm = model.java\njm.param().set('L', '1[m]')")
    assert r.ok, r.error
    assert comsol.current.name() == "beam"
    r = comsol.run("print(model.name(), jm is model.java)")  # later scripts see the same model
    assert r.ok and r.output.strip() == "beam True"
    comsol.run("cs.new_model('second')")
    assert comsol.current.name() == "second"
    assert comsol.fake_start.call_count == 1  # one COMSOL session for everything


def test_every_comsol_recipe_runs(comsol, tmp_path):
    assert len(recipes("comsol")) >= 2
    for heading, block in recipes("comsol"):
        r = comsol.run(block)
        assert r.ok, f"{heading}:\n{r.error}"
    assert "max velocity: 0.1 m/s" in r.output
    assert (tmp_path / "comsol").exists()


@pytest.fixture
def ansys(monkeypatch, tmp_path):
    mapdl = mock.MagicMock()
    pp = mapdl.post_processing
    pp.nodal_displacement.return_value = np.array([0.0, -0.001, -0.0025])
    pp.nodal_eqv_stress.return_value = np.array([1e6, 3e8])
    pp.nodal_temperature.return_value = np.linspace(100, 20, 21)
    mapdl.get_value.return_value = 42.0
    core = types.ModuleType("ansys.mapdl.core")
    core.launch_mapdl = mock.MagicMock(return_value=mapdl)
    for name, module in {"ansys": types.ModuleType("ansys"), "ansys.mapdl": types.ModuleType("ansys.mapdl"),
                         "ansys.mapdl.core": core}.items():
        monkeypatch.setitem(sys.modules, name, module)
    from jarvis.skills.ansys import AnsysSkill

    cfg = load_config()
    cfg.paths.projects = tmp_path
    skill = AnsysSkill(cfg)
    skill.fake = mapdl
    return skill


def test_every_ansys_recipe_runs_and_reports_results(ansys):
    assert len(recipes("ansys")) >= 3
    outputs = []
    for heading, block in recipes("ansys"):
        r = ansys.run(block)
        assert r.ok, f"{heading}:\n{r.error}"
        outputs.append(r.output)
    joined = "\n".join(outputs)
    assert "Max displacement (Y): 0.0025 m" in joined
    assert "Theory F L^3 / 3EI" in joined and "Max von Mises stress: 300 MPa" in joined
    assert "Temperature range: 20 to 100" in joined
    ansys.fake.antype.assert_any_call("STATIC")


def test_ansys_modal_helper(ansys):
    r = ansys.run("an.new('m')\nan.solve('MODAL', modes=3)\nan.frequencies(3)")
    assert r.ok, r.error
    ansys.fake.modopt.assert_called_with("LANB", 3)
    assert "Natural frequencies (Hz): 42, 42, 42" in r.output
