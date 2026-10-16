# Simple demo: don't trust the agent, check the phone

This is the smallest possible version of my QA agent design. One Python file, no cloud phone, runs on any laptop.

## The idea in one line

An agent does a task on a phone. Then a **separate checker looks at the phone itself** and decides if it worked. The agent's own "done" is never trusted.

## What is in here

| Piece | In the real design | In this demo |
|---|---|---|
| Phone | Mobilerun cloud phone | `FakePhone`, a Python object with 3 settings (wifi, dark theme, time zone) |
| Agent | Mobilerun's agent | Borrowed: **Claude** (with an API key) or 3 fake agents: honest, liar, flaky |
| Checker | reads `ui-state` / `timezone` through the API | `phone.read_setting(...)` |
| Direct path | the runner taps the toggle itself | the runner calls `phone.change_setting(...)` itself, no agent |
| Repeats | 3 | 3 |
| Step limit | `maxSteps` | `MAX_STEPS = 10` |

## What happens when you run it

For every scenario (for example "Turn on Wi-Fi"):

1. **Run the agent 3 times**, each time on a fresh phone (like a reset).
2. After each run the **checker reads the phone**. Not the agent's answer, the phone.
3. Decide with fixed rules:
   - all 3 runs really worked → **PASS**
   - the checker can't read it at all → **CAN'T TELL** (never a pass)
   - it failed → try the **direct path** (change the setting ourselves, no agent):
     - fails every time and the direct path also fails → **PRODUCT BUG** (the phone is broken)
     - otherwise → **AGENT MISTAKE** (the phone can do it, the agent didn't)

## Run it

No install needed for the tour:

```bash
python demo.py
```

The tour shows 4 situations, one after another:

| Situation | What you see |
|---|---|
| honest agent, working phone | PASS |
| honest agent, Wi-Fi broken on the phone | Wi-Fi is a **PRODUCT BUG** (the agent even says "done", but the phone didn't change) |
| liar agent (says done, does nothing) | **AGENT MISTAKE**. The agent said "Y" 3 times, the checker read "off" 3 times |
| flaky agent (only works on try 2) | **AGENT MISTAKE**. Passes 1 of 3, so the phone can do it |

The WhatsApp scenario is always **CAN'T TELL** because the fake phone has no way to show it. That's on purpose: when we can't check, we never call it a pass.

Try your own:

```bash
python demo.py --agent liar
python demo.py --agent flaky --broken timezone
```

## With a real AI agent (Claude)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python demo.py --agent claude
python demo.py --agent claude --broken wifi
```

Claude gets three tools: `look_at_screen`, `change_setting` and `finish(success, message)`. The demo doesn't care what Claude says in `finish`. It only looks at the phone.

With `--broken wifi`, Claude may notice that Wi-Fi didn't change and report failure, or it may just say "done". Either way the checker reads "off", the direct path also fails, and the result is **PRODUCT BUG**. That's the point: the verdict doesn't depend on the agent being honest or smart.

## How this maps to Mobilerun

Swap the fake parts for real ones and you get the design doc:

- `FakePhone` → a Mobilerun cloud phone
- `agent.run(...)` → `POST /tasks` to the Mobilerun agent
- `phone.read_setting(...)` → `GET /devices/{id}/timezone`, `ui-state`, ...
- direct path → `POST /devices/{id}/tap` and the other direct device calls

`../qa_check.py` in this repo is that real version for the time zone scenario.
