import ast
import importlib.util
import re
import sys

import pytest

from jarvis.config import load_config
from jarvis.llm import ChatResult
from jarvis.skills import RunResult, Skill
from jarvis.skills.agent import check_code, extract_code, run_task
from jarvis.skills.guides import available_guides, load_guide, script_guide, teaching_guide


class FakeSkill(Skill):
    name = "blender"  # borrow a real guide
    title = "FakeApp"
    where = "in a test"

    def __init__(self, config, results):
        super().__init__(config)
        self.results = list(results)
        self.ran = []

    def run(self, code):
        self.ran.append(code)
        return self.results.pop(0)

    def state(self):
        return "nothing open"


class ScriptedLLM:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, **kw):
        self.calls.append([dict(m) for m in messages])
        return ChatResult(content=self.replies.pop(0))


@pytest.fixture
def cfg(tmp_path):
    c = load_config()
    c.paths.data = tmp_path
    return c


def test_task_succeeds_first_time(cfg):
    llm = ScriptedLLM("```python\nprint('made a cube')\n```\nMakes a cube.")
    skill = FakeSkill(cfg, [RunResult(True, "made a cube\n")])
    result = run_task(skill, "make a cube", llm, cfg)
    assert result.ok and result.attempts == 1 and "made a cube" in result.summary
    assert skill.ran == ["print('made a cube')"]
    system = llm.calls[0][0]["content"]
    assert "FakeApp" in system and "nothing open" in system and "add_object" in system  # guide included
    assert result.script.exists() and "Task: make a cube" in result.script.read_text()


def test_errors_are_fed_back_and_fixed(cfg):
    said = []
    llm = ScriptedLLM("```python\nboom()\n```", "```python\nprint('fixed')\n```")
    skill = FakeSkill(cfg, [RunResult(False, "partial", "NameError: name 'boom' is not defined"),
                            RunResult(True, "fixed")])
    result = run_task(skill, "do it", llm, cfg, say=said.append)
    assert result.ok and result.attempts == 2
    fix_request = llm.calls[1][-1]["content"]
    assert "NameError" in fix_request and "partial" in fix_request
    assert said == ["First try hit a snag. Fixing it."]


def test_unsafe_or_missing_code_never_runs(cfg):
    llm = ScriptedLLM("I would do it like this.", "```python\nimport subprocess\n```",
                      "```python\nimport shutil\nshutil.rmtree('/')\n```", "```python\nx = (\n```")
    skill = FakeSkill(cfg, [])
    result = run_task(skill, "task", llm, cfg)
    assert not result.ok and skill.ran == []
    assert "SyntaxError" in result.summary


def test_extract_code():
    assert extract_code("text\n```python\na = 1\n```\nmore") == "a = 1"
    assert extract_code("```\nprint(1)\n```") == "print(1)"
    assert extract_code("<think>hmm</think>import bpy\nbpy.ops") == "import bpy\nbpy.ops"
    assert extract_code("Sorry, I can't.") == ""


def test_check_code_allows_normal_app_scripting():
    assert check_code("import math, os\nos.makedirs('x', exist_ok=True)\nbpy.data.objects.remove(o)") is None
    assert check_code("col.objects.unlink(o)\nitems.remove(3)") is None
    assert "os.system" in check_code("import os\nos.system('dir')")
    assert "rmtree" in check_code("from shutil import rmtree as r\nr('/')")
    assert "subprocess" in check_code("import subprocess")
    assert "eval" in check_code("eval('1')")


# ------------------------------------------------------------------ guides
def test_every_guide_parses_and_has_teaching_steps():
    assert set(available_guides()) >= {"blender", "solidworks", "comsol", "ansys", "canva"}
    for name in available_guides():
        intro, sections = load_guide(name)
        assert intro and sections, name
        if name != "canva":
            assert any(s.kind == "gui" for s in sections), name
            assert any(s.kind == "recipe" for s in sections), name


def test_all_guide_code_examples_are_valid_python():
    for name in available_guides():
        _, sections = load_guide(name)
        for section in sections:
            for block in re.findall(r"```python\n(.*?)```", section.body, flags=re.S):
                ast.parse(block, filename=f"{name}: {section.heading}")


def test_retrieval_picks_the_relevant_recipe():
    assert "Recipe: flange" in script_guide("solidworks", "make a flange by revolving a profile", recipes=1)
    assert "Recipe: 1D pipe flow" in script_guide("comsol", "create a 1D pipe flow model", recipes=1)
    assert "Recipe: cantilever" in script_guide("ansys", "cantilever beam deflection", recipes=1)
    assert "GUI: 1D pipe flow" in teaching_guide("comsol", "how do I set up 1D pipe flow by hand")
    assert "GUI: sketch tools" in teaching_guide("solidworks", "how do I draw a line in a sketch")


# ------------------------------------------------------------------ Blender (real)
bpy_available = importlib.util.find_spec("bpy") is not None
NO_RENDER = (
    "def render_animation(path, background=True):\n    print('render skipped', path)\n"
    "def render_image(path, frame=None):\n    print('render skipped', path)\n"
)


@pytest.mark.skipif(not bpy_available, reason="needs the bpy module (pip install bpy)")
def test_blender_guide_recipes_run_in_real_blender(tmp_path):
    from jarvis.skills.blender import BlenderSkill

    c = load_config()
    c.paths.projects = tmp_path
    c.skills.blender.executable = sys.executable
    skill = BlenderSkill(c)
    _, sections = load_guide("blender")
    ran = 0
    for section in sections:
        for block in re.findall(r"```python\n(.*?)```", section.body, flags=re.S):
            setup = "clear_scene()\nadd_object('cube', 'Product')\n" if "Product" in block else ""
            result = skill.run(NO_RENDER + setup + block)
            assert result.ok, f"{section.heading}:\n{result.error}"
            ran += 1
    assert ran >= 3
    assert (tmp_path / "blender" / "scene.blend").exists()
    assert "Text" in skill.state()  # the last recipe's 3D title is in the saved scene


@pytest.mark.skipif(not bpy_available, reason="needs the bpy module (pip install bpy)")
def test_voice_request_to_blender_end_to_end(tmp_path):
    """Main brain -> blender tool -> code model writes a script -> real Blender -> spoken answer."""
    from jarvis.assistant import Assistant

    from .fake_ollama import FakeOllama, pieces, tool_call

    def script(body):
        last = body["messages"][-1]
        if body["model"] == "qwen2.5-coder:7b":  # the code model
            return pieces("```python\nclear_scene()\nb = add_object('sphere', 'Ball', size=0.5)\n"
                          "set_material(b, 'red')\nprint(scene_summary())\n```\nMakes a red ball.")
        if last["role"] == "tool":
            return pieces("Your red ball is ready, sir.")
        return [tool_call("blender", task="Create a red sphere named Ball, 0.5 m across")]

    with FakeOllama(script, models=["qwen2.5:7b", "qwen2.5-coder:7b"]) as server:
        cfg = load_config()
        cfg.llm.host = server.url
        cfg.paths.data = tmp_path / "data"
        cfg.paths.projects = tmp_path / "projects"
        cfg.skills.blender.executable = sys.executable
        cfg.skills.blender.enabled = True
        a = Assistant(cfg, voice_input=False, voice_output=False)
        assert "blender" in a.tools.names()
        assert "Blender" in a.brain.system_prompt()
        a.respond("make a small red ball in blender")
        tool_result = next(m for m in a.brain.history if m["role"] == "tool")
        assert tool_result["content"].startswith("Success.")
        assert "Ball (MESH)" in tool_result["content"] and "Ball material" in tool_result["content"]
        assert a.brain.history[-1]["content"] == "Your red ball is ready, sir."
        code_request = next(r for r in server.requests if r["model"] == "qwen2.5-coder:7b")
        assert "add_object" in code_request["messages"][0]["content"]  # got the Blender guide
