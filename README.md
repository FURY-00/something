# Jarvis: a local, offline AI voice assistant

Say **"Hey Jarvis"** and talk to it. Jarvis listens, thinks, talks back in a
British voice, and works your laptop for you: it opens apps and websites, scrolls
Instagram Reels, writes abstracts and essays into Word documents, types for you,
controls music and volume, sets reminders and remembers things about you.

The AI runs **entirely on your laptop**. There's no cloud, no API key and no
subscription. After a one-time download, it works with Wi-Fi switched off.

```
             "Hey Jarvis, write an abstract on solar energy"
                                   |
  microphone --> wake word --> speech to text --> language model --> text to speech --> speakers
                (openWakeWord)   (Whisper)        (Ollama, local)      (Piper)
                                                        |
                                              tools = Jarvis's hands
                               apps, browser, keyboard, mouse, Word files,
                               media keys, timers, memory, offline Wikipedia
```

---

## Is this actually possible? (the honest answer)

**Mostly yes.** Here is how each part of the dream holds up:

| You want | Reality |
|---|---|
| **Works offline** | ✅ The brain, the ears, the voice and the wake word all run locally. **But** websites still need internet: Jarvis can scroll Reels for you, but Instagram itself won't load offline. |
| **Responds when I call it** | ✅ An always-on "Hey Jarvis" detector that uses almost no CPU. It also listens for follow-up questions after answering, without the wake word. |
| **Talks to me like Jarvis** | ✅ A calm, witty, British-butler personality with a natural neural voice. It remembers facts about you between sessions. |
| **Does everything I say** | ⚠️ It can do anything it has a *tool* for (the list is below). That's a lot, and new tools are short Python functions. It works the keyboard and mouse like a person would, but it can't see the screen unless you add a vision model. |
| **Immense intelligence, knows everything online** | ⚠️ This is the real limit. A model that fits on a laptop (7–8 billion parameters) is smart and knows a lot of general knowledge, but it's clearly weaker than ChatGPT or Claude. It makes mistakes, and its knowledge stops at its training date, so it has no news or weather. Two ways to push this: run a bigger model if your hardware allows, and add **offline Wikipedia** (all of it, millions of articles) so Jarvis can look facts up. |

The movie version doesn't exist yet, even with a data centre behind it. This gets
surprisingly close on a normal laptop, and everything stays private.

---

## What your laptop needs

| Your laptop | Recommended model (`config.yaml` → `llm.model`) | Feels like |
|---|---|---|
| 8 GB RAM, no GPU | `qwen2.5:3b` | Quick, basic smarts |
| **16 GB RAM** (most laptops) | **`qwen2.5:7b`** (default) or `llama3.1:8b` | Good all-rounder. Replies start in a few seconds. |
| NVIDIA GPU with 12 GB+ VRAM, or Mac with 32 GB | `qwen2.5:14b` | Noticeably smarter |
| NVIDIA GPU with 24 GB+ VRAM, or Mac with 64 GB | `qwen2.5:32b` | Very capable |

- **Disk:** about 6 GB for the default setup. Offline Wikipedia is optional and extra: about 50 GB for the full text-only English edition, with smaller editions available.
- **OS:** Windows 10/11, macOS 12+, or Linux (X11 session).
- **Python:** 3.10 or newer (3.12 is the safest choice).
- Any mic and speakers. A headset avoids Jarvis hearing itself.

Any Ollama model that supports **tool calling** works (for example Qwen, Llama 3.1+,
Mistral, or the Qwen3/gpt-oss "thinking" models with `think: false`). Newer models
come out all the time, so check [ollama.com/search?c=tools](https://ollama.com/search?c=tools).

---

## Install

The installer needs internet once, to download Python packages, Ollama and the
models. After that, everything runs offline.

### Windows

1. Install **Python 3.12** from <https://www.python.org/downloads/>. On the first installer screen, tick **"Add python.exe to PATH"**.
2. Download this project (**Code → Download ZIP**, then unzip it) or `git clone` it.
3. Open the project folder, click the address bar, type `powershell` and press Enter. Then run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
   ```
   This creates a virtual environment, installs everything, installs [Ollama](https://ollama.com) with winget and downloads all the models (several GB, so give it time).
4. Double-click **`start_jarvis.bat`** and say **"Hey Jarvis"**.

### macOS / Linux

```bash
git clone <this repo> jarvis && cd jarvis
bash scripts/install.sh
./start_jarvis.sh
```

- **macOS:** allow your Terminal app under *System Settings → Privacy & Security* for **Microphone** and **Accessibility**. Accessibility is what lets it press keys and scroll.
- **Linux:** keyboard and mouse control needs an **X11** session. On Ubuntu's login screen, choose *"Ubuntu on Xorg"*.

### Manual install (any OS)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps openwakeword      # see the note in requirements.txt
# install Ollama from https://ollama.com/download and make sure it's running
python -m jarvis --setup                # downloads all models once
python -m jarvis --check                # shows what works and what doesn't
python -m jarvis                        # go!
```

---

## Using Jarvis

Say **"Hey Jarvis"**, wait for the chime, then speak. When it finishes answering, it
listens for a few more seconds, so you can keep talking without the wake word.

| Try saying… | What happens |
|---|---|
| "Open Instagram Reels" → "next" → "like this one" → "pause" | Drives Reels in your browser (log in to Instagram in your browser first) |
| "Scroll reels automatically every 10 seconds" … "stop" | Hands-free doomscrolling |
| "Open YouTube Shorts", "next one", "mute" | Same thing for YouTube Shorts |
| "Write a 250-word abstract on the impact of AI on healthcare" | Writes it and opens it in Word (saved in `Documents/Jarvis`) |
| "Type an email to my professor asking for an extension" | Types it straight into the window you have open |
| "Explain the selected text" / "Summarise what I copied" | Reads your highlighted or copied text and answers |
| "Open Chrome", "Open VS Code", "Close Spotify" | Launches and quits apps (asks before closing) |
| "Search YouTube for lo-fi music", "Open Gmail" | Opens it in your browser |
| "Scroll down", "Press Ctrl+S", "Switch window", "Press Enter" | Keyboard and mouse control |
| "Pause the music", "Next song", "Volume 40 percent" | Media keys and volume |
| "What time is it?", "How's my battery?" | System information |
| "Set a timer for 10 minutes", "Remind me to drink water in 30 minutes" | Speaks up when the time is up |
| "Remember that my exam is on the 5th of October" | Remembers it permanently, even after a restart |
| "Take a screenshot" / "What's on my screen?" | Screenshot / vision (needs `vision_model`) |
| "Find my resume", "Open Downloads" | File search and opening |
| "Lock the computer", "Shut down" | Power controls (asks before shutting down) |
| "Explain black holes like I'm ten", "Who was Ashoka?" | Just a conversation |
| "Stop", "New conversation", "Goodbye" | Instant built-in commands |

Press **Ctrl+C** while it's talking to interrupt it, and **Ctrl+C** again when it's idle to quit.

### Other ways to run it

```bash
python -m jarvis --text            # type instead of talking (great for testing)
python -m jarvis --text --mute     # type, and no voice either
python -m jarvis --push-to-talk    # press Enter, then speak (no wake word)
python -m jarvis --model llama3.1:8b
python -m jarvis --list-devices    # pick a different mic/speaker in config.yaml
python -m jarvis --check           # diagnose problems
```

Everything else, including name, voice, speed, wake word sensitivity and model, is in **`config.yaml`**.
Want it called "Friday" and calling you "Boss"? Change `assistant_name` and `user_title`.
Then set `wake_word.engine: whisper`, which reacts to the name instead of the built-in "Hey Jarvis" model.

---

## Making Jarvis smarter

**1. A bigger brain.** Pull a bigger model and put its name in `config.yaml`:
```bash
ollama pull qwen2.5:14b
```

**2. Offline Wikipedia, the "knowledge of everything" part.**
[Kiwix](https://kiwix.org) serves the whole of Wikipedia from one file, offline.
1. Download a Wikipedia `.zim` file from <https://library.kiwix.org>. For example, "Wikipedia English, no pictures" (big but complete) or a smaller "top articles" edition.
2. Download **kiwix-tools** from <https://kiwix.org/en/applications/> and run:
   ```bash
   kiwix-serve --port 8080 wikipedia_en_all_nopic_XXXX-XX.zim
   ```
3. In `config.yaml` set `knowledge: kiwix_url: http://localhost:8080`.

Jarvis now looks up facts before answering, instead of relying on memory alone.
Kiwix also has offline Stack Overflow, Wiktionary, medical encyclopedias and more.
Any of them work the same way.

**3. Eyes.** Set `vision_model: qwen2.5vl:7b` (or `gemma3:4b` on smaller machines) and run
`ollama pull` for it. Then ask "what's on my screen?" or "read this error message".

**4. Better hearing.** If it mishears you, change `stt.model` from `base.en` to `small.en`,
then run `python -m jarvis --setup` again.

---

## Adding your own abilities

Every ability is a normal Python function. For example, add this to
`jarvis/tools/system.py`:

```python
@tool(
    "Open my college timetable.",   # the model reads this to decide when to use it
)
def open_timetable(ctx) -> str:
    open_with_default_app(r"C:\Users\me\Documents\timetable.pdf")
    return "Opened the timetable."
```

Arguments are described with JSON schema, and the model fills them in:

```python
@tool("Send a WhatsApp message.", {
    "contact": {"type": "string", "description": "Who to message"},
    "text": {"type": "string", "description": "The message"},
})
def whatsapp(ctx, contact: str, text: str) -> str:
    ...
```

Use `ctx.confirm("Are you sure?")` before anything risky, and `ctx.say("On it")`
for progress updates. A new file in `jarvis/tools/` also needs adding to
`TOOL_MODULES` in `jarvis/tools/__init__.py`.

---

## Privacy and safety

- The AI, the voice recognition and the voice all run on your machine. Nothing you say leaves your laptop. The only exception is a website you ask it to open, which your browser loads as usual.
- Jarvis **asks first** before shutting down, restarting, closing apps or closing windows (`safety.confirm_dangerous`).
- Running terminal commands is **off** by default (`safety.allow_shell`). When it's on, Jarvis still asks before every command.
- Emergency stop for keyboard and mouse control: slam the mouse into a **screen corner**, or press Ctrl+C.
- Memory lives in `data/memory.json`. Read it, edit it, or say "forget …".

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Can't reach Ollama" | Open the Ollama app (Windows/macOS) or run `ollama serve` |
| "model isn't downloaded" | `ollama pull qwen2.5:7b` (or whatever your `llm.model` is) |
| Doesn't react to "Hey Jarvis" | Lower `wake_word.threshold` to `0.3`, check the mic with `--list-devices`, or use `--push-to-talk` |
| Wakes up by itself | Raise `wake_word.threshold` to `0.7` |
| Never stops listening | Raise `audio.min_speech_rms` (for example 600) in a noisy room |
| Cuts you off mid-sentence | Raise `audio.silence_seconds` to `1.5` |
| Mishears you | `stt.model: small.en`, then `--setup` again |
| Replies are slow | Use a smaller model, or a GPU. The first reply is always slower while the model loads. |
| Picks the wrong action | Say it more directly ("open the website instagram.com"), or use a bigger model |
| Keyboard control does nothing | macOS: allow Accessibility. Linux: use X11. Windows: it can't control apps running as administrator unless Jarvis is too. |
| Robotic voice | Piper voice missing, so it fell back to the system voice. Run `--setup`. |

---

## Honest limitations

- A laptop-sized model is clever but fallible. It sometimes misunderstands requests, picks the wrong tool, or states wrong facts confidently. Offline Wikipedia and bigger models reduce this.
- It has no live information (news, weather, prices) unless you ask it to open a website.
- It controls apps "blind", through the keyboard and mouse. If a website redesigns itself, a shortcut might stop working.
- You can't interrupt it by voice mid-sentence. Use Ctrl+C or keep your questions short.
- It's tuned for English. For other languages, use a multilingual `stt.model` (such as `small`) and a Piper voice in that language.

---

## Project layout

```
jarvis/
  __main__.py      command line: python -m jarvis
  assistant.py     main loop: wake word -> listen -> think -> speak
  brain.py         personality, conversation memory, tool calling
  llm.py           talks to the local Ollama server
  audio.py         microphone + detecting when you start/stop speaking
  wakeword.py      "Hey Jarvis" (openWakeWord), name spotting, push-to-talk
  stt.py           speech to text (faster-whisper)
  tts.py           text to speech (Piper, with the system voice as a fallback)
  memory.py        long-term memory
  setup_models.py  --setup downloads and --check diagnostics
  tools/           everything Jarvis can do (apps, web, keyboard, writing, ...)
config.yaml        your settings
tests/             run with: pip install pytest && python -m pytest
```

Built on [Ollama](https://ollama.com), [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
[openWakeWord](https://github.com/dscripka/openWakeWord), [Piper](https://github.com/OHF-Voice/piper1-gpl),
[PyAutoGUI](https://github.com/asweigart/pyautogui) and [Kiwix](https://kiwix.org).
