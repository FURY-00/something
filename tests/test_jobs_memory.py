import subprocess
import sys
import threading

from jarvis.brain import Brain
from jarvis.config import load_config
from jarvis.context import ToolContext
from jarvis.jobs import JobManager
from jarvis.llm import ChatResult
from jarvis.memory import Memory
from jarvis.tools import ToolRegistry


def test_background_job_announces_and_shows_in_summary():
    done = threading.Event()
    heard = []
    jobs = JobManager(lambda text: (heard.append(text), done.set()))
    jobs.start("render", lambda: (True, "saved to out.mp4"))
    assert done.wait(5)
    assert heard == ["The render job is finished."]
    assert "render (started" in jobs.summary() and "done - saved to out.mp4" in jobs.summary()


def test_failed_job_says_so():
    done = threading.Event()
    heard = []
    jobs = JobManager(lambda text: (heard.append(text), done.set()))

    def boom():
        raise RuntimeError("solver diverged")

    jobs.start("simulation", boom)
    assert done.wait(5)
    assert "failed" in heard[0] and "solver diverged" in heard[0]


def test_watching_an_outside_process():
    done = threading.Event()
    heard = []
    jobs = JobManager(lambda text: (heard.append(text), done.set()))
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.3)"])
    jobs.watch_process("animation render", proc.pid, "/tmp/ball.mp4")
    assert done.wait(10)
    proc.wait()
    assert heard == ["The animation render is finished. It's saved at /tmp/ball.mp4."]


class Echo:
    def __init__(self, reply="ok"):
        self.reply = reply
        self.sent = []

    def chat(self, messages, **kw):
        self.sent.append(messages)
        return ChatResult(content=self.reply)


def make_brain(tmp_path, llm, apps=None):
    cfg = load_config()
    memory = Memory(tmp_path / "m.json")
    ctx = ToolContext(cfg, llm, memory)
    jobs = JobManager(lambda t: None)
    brain = Brain(cfg, llm, ToolRegistry(ctx, {}), memory, "Windows 11", speak=lambda s: None,
                  show=lambda s: None, jobs=jobs, apps=apps)
    return brain, memory, jobs


def test_system_prompt_has_personality_apps_memories_and_jobs(tmp_path):
    brain, memory, jobs = make_brain(tmp_path, Echo(), apps=["SolidWorks", "COMSOL Multiphysics"])
    memory.add("The user studies mechanical engineering.")
    memory.add_episode("23 Sep 2026", "We modelled a flange in SolidWorks; stress check still to do.")
    jobs.jobs.append(type("J", (), {"name": "COMSOL task", "status": "running", "result": "",
                                    "started": __import__("datetime").datetime.now()})())
    prompt = brain.system_prompt()
    assert "clever, warm friend" in prompt
    assert "Professional applications you can work in: SolidWorks, COMSOL Multiphysics." in prompt
    assert "- The user studies mechanical engineering." in prompt
    assert "23 Sep 2026: We modelled a flange" in prompt
    assert "Background jobs:" in prompt and "COMSOL task" in prompt
    assert "You run offline" in prompt


def test_conversation_summary_needs_a_real_conversation(tmp_path):
    llm = Echo("We talked about their COMSOL pipe model.")
    brain, memory, _ = make_brain(tmp_path, llm)
    brain.history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello"}]
    assert brain.summarize() == ""  # one exchange isn't worth remembering
    brain.history += [{"role": "user", "content": "set up a pipe model"},
                      {"role": "assistant", "content": "Done."}]
    assert brain.summarize() == "We talked about their COMSOL pipe model."
    transcript = llm.sent[0][1]["content"]
    assert "User: set up a pipe model" in transcript and "Jarvis: Done." in transcript


def test_cloud_brain_history_is_never_edited(tmp_path):
    llm = Echo()
    llm.append_only = True
    brain, _, _ = make_brain(tmp_path, llm)
    long_output = "x" * 5000
    brain.history = [{"role": "user", "content": "a"},
                     {"role": "assistant", "content": "", "tool_calls": []},
                     {"role": "tool", "content": long_output, "tool_name": "t"},
                     {"role": "assistant", "content": "done"}]
    brain.handle("b")
    sent = llm.sent[0]
    assert sent[3]["content"] == long_output
    assert "no live news" in sent[0]["content"] and "You run offline" not in sent[0]["content"]


def test_memory_file_keeps_facts_and_episodes(tmp_path):
    m = Memory(tmp_path / "m.json")
    m.add("likes tea")
    for i in range(35):
        m.add_episode("1 Jan", f"chat {i}")
    again = Memory(tmp_path / "m.json")
    assert again.facts == ["likes tea"] and len(again.episodes) == 30
    assert again.episodes_prompt(2) == "- 1 Jan: chat 33\n- 1 Jan: chat 34"
