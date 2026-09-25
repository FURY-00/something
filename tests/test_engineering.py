"""Engineering calculator (really runs Python) and the study notes."""

import re

import pytest

from jarvis.config import load_config
from jarvis.skills.calc import CalcSkill
from jarvis.skills.guides import knowledge_subjects, load_guide, search_knowledge

pytest.importorskip("scipy")
pytest.importorskip("sympy")


@pytest.fixture
def calc(tmp_path):
    cfg = load_config()
    cfg.paths.projects = tmp_path
    return CalcSkill(cfg)


def recipe_outputs(calc):
    _, sections = load_guide("calc")
    out = {}
    for s in sections:
        for block in re.findall(r"```python\n(.*?)```", s.body, flags=re.S):
            r = calc.run(block)
            assert r.ok, f"{s.heading}:\n{r.error}"
            out[s.heading] = r.output
    return out


def test_calculator_recipes_run_and_give_textbook_answers(calc, tmp_path):
    out = recipe_outputs(calc)
    beam = out["Recipe: beam bending, deflection and stress"]
    assert "max bending stress = 30.0 MPa" in beam            # M c / I = 2500 * 0.05 / 4.167e-6
    assert "Mid-span deflection = 1.000 mm" in beam           # 5000 * 8 / (48 * 200e9 * 4.167e-6)
    assert "turbulent" in out["Recipe: pipe flow pressure drop (Colebrook equation)"]
    vib = out["Recipe: vibration of a damped spring-mass system (ODE)"]
    assert "Natural frequency 20.00 rad/s" in vib and "damping ratio 0.100" in vib
    assert (tmp_path / "calculations" / "free_vibration.png").exists()
    sym = out["Recipe: symbolic derivation with sympy"]
    assert "5*L**4*w/(384*E*I)" in sym.replace(" ", "")
    truss = out["Recipe: 2D truss by the stiffness method"]
    assert "should be 10" in truss and "sum to 10.00 kN" in truss
    assert truss.count("compression") == 2 and truss.count("tension") == 1
    cycle = out["Recipe: thermodynamic cycle with an ideal gas"]
    assert "thermal efficiency = 48.2 %" in cycle and "formula: 48.2 %" in cycle


def test_failed_calculation_reports_the_error(calc):
    r = calc.run("x = 1 / 0")
    assert not r.ok and "ZeroDivisionError" in r.error


def test_study_notes_cover_core_subjects():
    subjects = set(knowledge_subjects())
    assert {"mechanics_of_materials", "thermodynamics", "fluid_mechanics", "heat_transfer",
            "machine_design", "dynamics_vibrations", "materials_manufacturing", "fea_cfd_methods"} <= subjects
    assert "Mohr's circle" in search_knowledge("explain mohr circle and principal stresses")
    assert "Goodman" in search_knowledge("fatigue failure with mean stress")
    assert "Hagen-Poiseuille" in search_knowledge("laminar pipe flow pressure drop")
    assert "Biot" in search_knowledge("lumped capacitance transient cooling")
    assert "Rankine" in search_knowledge("steam power plant cycle efficiency")
    assert "Euler critical load" in search_knowledge("column buckling")
    assert "Mesh convergence" in search_knowledge("how do I know my FEA mesh is fine enough")
