# Jarvis: your AI voice assistant for engineering and everyday work

Say **"Hey Jarvis"** and talk to it like a person. Jarvis chats with you, remembers
what you worked on together, and does real work on your computer:

- **SolidWorks**: sketches from the geometry you describe, extrudes, cuts, revolves, fillets, holes, materials, exports
- **COMSOL**: builds models (1D pipe flow, laminar flow, heat transfer, stress), meshes, solves, reports numbers
- **Ansys**: beam, truss, thermal, plate and modal analyses through MAPDL, with results checked against hand calculations
- **Canva**: finds your designs and changes text, sizes, colours, backgrounds and images, and asks before saving
- **Blender**: builds scenes, animates and renders videos
- **Code**: writes Python, JavaScript, C and more; builds interactive **websites from your PDFs, PowerPoints and Word files**
- Everyday tasks: apps, websites, Instagram Reels, typing, music, timers, documents, screenshots

It's also a **mechanical engineering tutor**. It explains core concepts (statics, strength of
materials, dynamics and vibrations, thermodynamics, fluids, heat transfer, machine design,
materials, FEA/CFD) with intuition, equations, worked examples and quick questions. It solves real
problems by **writing and running Python** (numpy, scipy, sympy), so the numbers are computed, not
guessed. And "how do I set up 1D pipe flow in COMSOL?" walks you through the clicks step by step.

```
 "Hey Jarvis, sketch a 50 mm equilateral triangle on the front plane and extrude it 10 mm"
                                   |
 microphone -> wake word -> speech to text -> conversation brain -> text to speech -> speaker
                                                     |
                                     solidworks("...full task...")
                                                     |
                          code brain + SolidWorks guide -> writes a script
                                                     |
                           runs inside SolidWorks -> error? -> fixes it -> runs again
```

---

## Can it really do all this? (the honest answer)

**Yes for the workflow, with one big caveat about intelligence.**

| You want | Reality |
|---|---|
| Talks like a person | ✅ A warm, witty personality that reacts, asks follow-up questions and remembers past conversations ("last time we were on your flange model..."). |
| Draws in SolidWorks from geometry you describe | ✅ Through the SolidWorks API, which is far more reliable than clicking. Lines, circles, arcs, polygons, slots, extrudes, cuts, revolves, fillets, chamfers, shells, planes, materials, dimension edits, STEP/STL export. Windows only. |
| 1D flow in COMSOL / Ansys | ✅ COMSOL through its official Java API (the one "Record Method" uses). 1D pipe flow needs COMSOL's **Pipe Flow Module**; without it, Jarvis can do 2D axisymmetric pipe flow on the base licence. Ansys through PyMAPDL: 1D lines (beams, trusses, heat conduction, pipe elements), 2D and 3D. **Fluent CFD** and Workbench are taught step by step, not automated. |
| Changes fonts or backgrounds in Canva | ⚠️ Mostly. Through Canva's official connector: text, **font size**, colour, bold, italic, alignment, element and background colours, images, layout. But Canva's connector **can't change the font family** (the typeface itself) right now; Jarvis will say so and offer the closest change. Canva is online-only, so this part needs internet. |
| Websites from PDFs/PPTs, and any code | ✅ It reads your documents (text and images) and builds a complete interactive site: navigation, quizzes, search, charts. It writes programs in any language and runs and fixes Python itself. |
| "Knows every tool of these programs" | ⚠️ **This is the real limit.** Jarvis ships with a hand-written guide for each app (API essentials, worked recipes, and click-by-click steps for the main tools), and it fixes its own errors by reading them. But a model small enough to run on a laptop makes mistakes on complex CAD/CAE work. For serious engineering, switch the **code brain to Claude** (below). It knows these APIs far better. Simple and moderate tasks work best; for big projects, Jarvis breaks the work into steps and checks in with you. |
| Fully offline | ✅ The default (local brain), except Canva and websites, which need internet. The optional Claude brain needs internet. |

Every script Jarvis writes is saved (`data/scripts/`), so you can see exactly what it did, and
scripts are checked before they run so they don't delete files or run commands.

---

## Two brains: local or Claude

Jarvis uses two brains, and each can be local or cloud (`config.yaml`):

| | Local (Ollama) | Claude (Anthropic API) |
|---|---|---|
| Conversation (`llm.provider`) | Private, free, offline. Good small talk and everyday tasks | Much smarter conversation |
| Code & app scripts (`skills.code_provider`) | `qwen2.5-coder:7b` / `14b`: fine for Blender, simple parts and websites | **Recommended for SolidWorks, COMSOL and Ansys**: knows the APIs, writes much better scripts and sites |
| Needs | 16 GB RAM for 7B models | Internet + an API key, paid per use |

A good setup is local for conversation and Claude for the heavy work:

```yaml
llm:
  provider: ollama
skills:
  code_provider: anthropic
```

Then set your key once. On Windows: `setx ANTHROPIC_API_KEY "sk-ant-..."`; on macOS/Linux, add
`export ANTHROPIC_API_KEY=...` to your shell profile. Get a key at <https://console.anthropic.com>.
Voice, wake word and speech recognition always stay on your laptop.

---

## What your laptop needs

| Your laptop | Local conversation model | Local code model |
|---|---|---|
| 8 GB RAM | `qwen2.5:3b` | use Claude for code |
| **16 GB RAM** | **`qwen2.5:7b`** (default) | **`qwen2.5-coder:7b`** (default) |
| NVIDIA GPU 12 GB+ / Mac 32 GB | `qwen2.5:14b` | `qwen2.5-coder:14b` |
| NVIDIA GPU 24 GB+ / Mac 64 GB | `qwen2.5:32b` | `qwen2.5-coder:32b` |

- **Disk:** about 11 GB for the default local setup.
- **OS:** Windows 10/11 (needed for SolidWorks), macOS 12+ or Linux (X11). Python 3.10+ (3.12 is safest).
- The apps themselves: SolidWorks, COMSOL, Ansys and Blender must be installed and licensed as usual. Jarvis only drives them.

---

## Install

### Windows

1. Install **Python 3.12** from <https://www.python.org/downloads/> and tick **"Add python.exe to PATH"**.
2. Download this project (**Code → Download ZIP**, then unzip it) or `git clone` it.
3. In the project folder, click the address bar, type `powershell`, press Enter, then run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```
   This installs everything, including [Ollama](https://ollama.com), and downloads the models (several GB).
4. Double-click **`start_jarvis.bat`** and say **"Hey Jarvis"**.

### macOS / Linux

```bash
git clone <this repo> jarvis && cd jarvis
bash scripts/install.sh
./start_jarvis.sh
```
macOS: allow your Terminal under *System Settings → Privacy & Security* for **Microphone** and
**Accessibility**. Linux: use an **X11** session (on Ubuntu's login screen, pick *"Ubuntu on Xorg"*).

### Manual install (any OS)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps openwakeword
pip install ansys-mapdl-core            # only if you have Ansys
python -m jarvis --setup                # downloads all models once
python -m jarvis --check                # shows what works, including which apps were found
python -m jarvis
```

---

## Setting up each application

Run `python -m jarvis --check` to see which ones Jarvis found.

**SolidWorks (Windows).** Nothing to set up: Jarvis connects to SolidWorks (or starts it) through
its COM API. Keep SolidWorks' default part template configured (*Tools → Options → Default Templates*).

**COMSOL.** Installed automatically via the `mph` package. If you have several COMSOL versions, set
`skills.comsol.version: "6.2"`. The first request starts a COMSOL session, which takes about a minute.
Tip: COMSOL's *Developer → Record Method* shows the exact API for any GUI step. Jarvis's guide explains this too.

**Ansys.** `pip install ansys-mapdl-core` (the installer does it when Ansys is found). Ansys
Student editions generally work too. If MAPDL isn't found, set `skills.ansys.executable` to the path of `ANSYS242.exe` (or similar).

**Canva.** The first Canva request opens your browser to sign in to Canva and approve Jarvis.
The login is saved in `data/mcp/canva.json`, so you stay signed in; delete that file to sign out.
This uses Canva's official connector at `https://mcp.canva.com/mcp`.

**Blender.** Found automatically in the usual install folders, or set `skills.blender.executable`.
To watch Jarvis build in your open Blender window, install the add-on: *Edit → Preferences →
Add-ons → Install from Disk* → `jarvis/skills/blender_addon.py`, then tick **Jarvis Bridge**.
Without the add-on, Jarvis works in the background and saves the scene in `Documents/Jarvis/Projects/blender/`.

---

## Things to say

| Try saying… | What happens |
|---|---|
| "Sketch a 60 by 40 millimetre rectangle on the top plane and extrude it 8 mm" | New part, sketch, boss extrude |
| "Add four 6 mm holes, 10 mm in from each corner, all the way through" | Sketch on the face, cut through all |
| "Round the vertical edges with a 3 mm fillet, make it aluminium, and tell me the mass" | Fillet, material, mass properties |
| "Change the plate thickness to 12 mm" | Finds the dimension and edits it |
| "Export it as STEP to my desktop" | Save As STEP |
| "Set up a 1D pipe flow in COMSOL: 10 m long, 5 cm diameter, water, 2 kPa pressure drop" | Builds the model, asks if a detail is missing, solves, reports velocity and flow |
| "Run a cantilever beam in Ansys: 1 m steel, 30 mm square, 1 kN at the tip" | Solves and compares with PL³/3EI |
| "In Canva, make the title on my birthday poster bigger and gold" | Finds the design, edits a draft, shows a preview, saves when you say yes |
| "Change the background of the second page to dark blue" | Recolours the page's background shape (when the design has one) |
| "Make an interactive website from my thermodynamics lecture PDF, with a quiz" | Reads the PDF (text and images), builds the site, opens it |
| "Add a dark mode to that website" | Edits it and keeps a backup |
| "Write a Python script that plots the stress-strain curve from data.csv, and run it" | Writes, runs, fixes |
| "Make a bouncing ball animation in Blender and render it" | Scene, animation, MP4 rendered in the background |
| "How do I make a revolve in SolidWorks?" | Walks you through the clicks, step by step |
| "Teach me Mohr's circle" / "Why do shafts fail in fatigue?" | A lesson: intuition, equation, example, then a question for you |
| "A 2 m steel beam carries 5 kN at mid-span, 50 by 100 mm section. Stress and deflection?" | Writes and runs the calculation, explains each step |
| "Plot the response of a spring-mass system with 10 percent damping" | Solves the ODE and opens the graph |
| "Check this column for buckling in Ansys and compare with Euler" | Eigenvalue buckling vs hand formula |
| "Make a flange with six M8 holes on a 90 mm bolt circle, then a PDF drawing" | Revolve/extrude, bolt circle, 3-view drawing |
| Everyday: "Open Instagram Reels", "next", "Write a 250-word abstract on…", "Pause the music", "Remind me in 20 minutes" | Same as before |

Long jobs (renders, big solves) run **in the background** ("I'll tell you when it's done") so you
can keep talking. Press **Ctrl+C** while Jarvis is talking to interrupt it, and again when idle to quit.

### Other ways to run it

```bash
python -m jarvis --text            # type instead of talking
python -m jarvis --push-to-talk    # press Enter, then speak
python -m jarvis --model llama3.1:8b
python -m jarvis --check           # diagnose problems
```

---

## How Jarvis knows engineering

- **Study notes** in `jarvis/knowledge/*.md` cover the core of a mechanical engineering degree:
  equations with units, typical values, intuition and common mistakes. Jarvis looks up the relevant
  section before teaching, so formulas are right.
- **The calculator** (`solve_engineering`) writes a Python script for each problem, runs it and reads
  the answer, printing intermediate steps and a sanity check (a limiting case or a textbook formula).
  Plots are saved in `Documents/Jarvis/Projects/calculations/`.
- For the hardest problems (multi-step design, unusual physics), the Claude brain reasons far better
  than a local model. Still check anything safety-critical yourself.

## How Jarvis knows these programs

Each application has a guide in `jarvis/skills/guides/` (`solidworks.md`, `comsol.md`, `ansys.md`,
`canva.md`, `blender.md`):

- **API essentials and helpers**: always given to the code brain before it writes a script
- **`## Recipe:` sections**: worked examples; the most relevant ones are picked for each task
- **`## GUI:` sections**: click-by-click steps for teaching you by hand (`how_to`)

Helper libraries (`jarvis/skills/solidworks.py`, `comsol.py`, `ansys.py`, `blender_helpers.py`) wrap
the error-prone API calls. For example, SolidWorks' 23-argument `FeatureExtrusion2` becomes `sw.extrude(10)`.

**Teach Jarvis more** by adding a `## Recipe:` or `## GUI:` section to a guide in plain Markdown,
for example your lab's standard COMSOL setup or your company's SolidWorks conventions. That's the
best way to make it an expert in exactly what you do.

---

## Privacy and safety

- By default the brain, voice recognition and voice run on your machine. Canva, websites you open
  and the optional Claude brain use the internet.
- Scripts that Jarvis writes are checked before running: no deleting files, no shell commands, no
  network. This is a safety net against mistakes, not a sandbox. Every script is saved in
  `data/scripts/<app>/`.
- Jarvis **asks first** before shutting down, closing apps, saving Canva changes, or running a program
  that does something sensitive. Terminal commands are off by default (`safety.allow_shell`).
- Memory (facts and conversation summaries) lives in `data/memory.json`: read it, edit it, or say "forget …".

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Can't reach Ollama" | Open the Ollama app, or run `ollama serve` |
| An app isn't used ("I can't do that in SolidWorks") | `python -m jarvis --check` shows why it wasn't found; set `enabled: true` or the executable path in `config.yaml` |
| SolidWorks/COMSOL/Ansys results are wrong or it keeps failing | Use Claude as the code brain (`skills.code_provider: anthropic`), give exact numbers and units, and do it in smaller steps |
| COMSOL says a feature type is unknown | That physics needs a module you don't have (e.g. Pipe Flow), or the name differs in your version. Jarvis tries to discover names; the base-licence recipes are an alternative |
| Canva sign-in loop | Delete `data/mcp/canva.json` and try again |
| Doesn't react to "Hey Jarvis" | Lower `wake_word.threshold` to `0.3`, or use `--push-to-talk` |
| Never stops listening | Raise `audio.min_speech_rms` (e.g. 600) |
| Mishears you | `stt.model: small.en`, then `python -m jarvis --setup` |
| Slow replies | Smaller local model, a GPU, or Claude with `anthropic_effort: low` |

---

## Honest limitations

- A laptop-sized model can pick the wrong approach on complex CAD/CAE tasks; Claude does much better
  but costs money and needs internet. Always check engineering results before relying on them.
  Jarvis prints hand-calculation comparisons where it can.
- SolidWorks automation covers part modelling well. Assemblies, drawings, sweeps and lofts use raw API
  calls with long argument lists that vary by version, so expect more retries there.
- Canva: no typeface changes through the connector, and it needs internet.
- Fluent CFD and Workbench projects are taught step by step, not automated.
- It controls apps through their APIs, so it can't see your screen unless you add a vision model.
- Premiere Pro / DaVinci Resolve editing isn't included yet. It's the next skill to add.

---

## Project layout

```
jarvis/
  assistant.py       main loop: wake word -> listen -> think -> speak
  brain.py           personality, conversation memory, tool calling
  llm.py, llm_cloud.py  local (Ollama) and cloud (Claude) brains
  jobs.py            background jobs (renders, solves) with announcements
  mcp_bridge.py      connectors (Canva) over the Model Context Protocol
  documents.py       reads PDF / PowerPoint / Word / HTML (text + images)
  skills/
    agent.py         write -> run -> fix loop for application scripts
    guides/*.md      what Jarvis knows about each application
    solidworks.py comsol.py ansys.py blender.py canva.py web.py
    blender_helpers.py blender_addon.py
  tools/             everything Jarvis can do (apps, web, keyboard, writing, skills...)
  audio.py stt.py tts.py wakeword.py memory.py setup_models.py
config.yaml          your settings
tests/               pip install pytest && python -m pytest
```

Built on [Ollama](https://ollama.com), [Claude](https://www.anthropic.com/api),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), [openWakeWord](https://github.com/dscripka/openWakeWord),
[Piper](https://github.com/OHF-Voice/piper1-gpl), [MPh](https://mph.readthedocs.io),
[PyMAPDL](https://mapdl.docs.pyansys.com), the [Model Context Protocol](https://modelcontextprotocol.io)
and [PyAutoGUI](https://github.com/asweigart/pyautogui).
