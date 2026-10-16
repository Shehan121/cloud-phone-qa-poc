"""
Simple demo of my QA idea : the agent does a task on a phone , then a separate
checker looks at the phone itself. The agent never grades its own work.

The phone is fake (a Python object) so this runs on any laptop. The agent is
borrowed , Claude or one of three fake agents (honest , liar , flaky).

Run:
    python demo.py                 # tour: shows every outcome with fake agents
    python demo.py --agent claude  # use Claude as the agent (needs ANTHROPIC_API_KEY)
    python demo.py --agent honest --broken wifi
"""

import argparse
import os

REPEATS = 3   # every scenario runs 3 times, like in the design doc
MAX_STEPS = 10  # like maxSteps on Mobilerun: the agent gets at most 10 steps


# ---------------------------------------------------------------- the phone
class FakePhone:
    """A pretend phone. `broken` lists settings that ignore changes (a product bug)."""

    def __init__(self, broken=()):
        self.settings = {"wifi": "off", "dark_theme": "off", "timezone": "Europe/Berlin"}
        self.broken = set(broken)

    def change_setting(self, name, value):
        if name not in self.settings:
            return f"there is no setting called {name}"
        if name in self.broken:
            return "ok"  # the bug: it says ok, but nothing changes
        self.settings[name] = value
        return "ok"

    def read_setting(self, name):
        """What the checker uses. Returns None if the phone can't tell us."""
        return self.settings.get(name)


# ------------------------------------------------------------ the scenarios
# Each scenario = a task in plain words + the setting the checker reads + the value we expect.
SCENARIOS = [
    {"task": "Turn on Wi-Fi.", "setting": "wifi", "expected": "on"},
    {"task": "Turn on dark theme.", "setting": "dark_theme", "expected": "on"},
    {"task": "Change the time zone to Tokyo.", "setting": "timezone", "expected": "Asia/Tokyo"},
    # The phone has no setting for this, so the checker can't read it -> can't tell.
    {"task": "Send 'hi' to Anna in WhatsApp.", "setting": "whatsapp_last_message", "expected": "hi"},
]


# --------------------------------------------------------------- the agents
# Every agent has the same shape: run(scenario, phone, attempt) -> (says_success, message)

class HonestAgent:
    """Fake agent that really does the task."""
    def run(self, scenario, phone, attempt):
        phone.change_setting(scenario["setting"], scenario["expected"])
        return True, "done"


class LiarAgent:
    """Fake agent that says 'done' but never touches the phone."""
    def run(self, scenario, phone, attempt):
        return True, "done (but I did nothing)"


class FlakyAgent:
    """Fake agent that only does the job on the 2nd try."""
    def run(self, scenario, phone, attempt):
        if attempt == 2:
            phone.change_setting(scenario["setting"], scenario["expected"])
        return True, "done"


class ClaudeAgent:
    """The borrowed real agent: Claude with three tools to control the fake phone."""

    TOOLS = [
        {"name": "look_at_screen", "description": "See all current phone settings.",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "change_setting", "description": "Change one phone setting.",
         "input_schema": {"type": "object",
                          "properties": {"name": {"type": "string"}, "value": {"type": "string"}},
                          "required": ["name", "value"]}},
        {"name": "finish", "description": "Call this when you are done.",
         "input_schema": {"type": "object",
                          "properties": {"success": {"type": "boolean"}, "message": {"type": "string"}},
                          "required": ["success", "message"]}},
    ]

    def __init__(self):
        import anthropic  # only needed for this agent
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key.startswith("sk-ant-") or key.endswith("..."):
            raise SystemExit("Set a real key first: export ANTHROPIC_API_KEY=<your key from console.anthropic.com>")
        self.client = anthropic.Anthropic()
        self.model = os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5")

    def run(self, scenario, phone, attempt):
        messages = [{"role": "user", "content":
                     f"You control a phone. Task: {scenario['task']} "
                     "Settings use values like 'on'/'off' and IANA time zones. "
                     "Call finish when done."}]
        for _ in range(MAX_STEPS):
            reply = self.client.messages.create(model=self.model, max_tokens=500,
                                                tools=self.TOOLS, messages=messages)
            messages.append({"role": "assistant", "content": reply.content})
            results = []
            for block in reply.content:
                if block.type != "tool_use":
                    continue
                if block.name == "finish":
                    return bool(block.input["success"]), block.input["message"]
                if block.name == "look_at_screen":
                    out = str(phone.settings)
                else:
                    out = phone.change_setting(block.input["name"], block.input["value"])
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            if not results:  # the model answered in text without calling finish
                return False, "stopped without calling finish"
            messages.append({"role": "user", "content": results})
        return False, f"hit the {MAX_STEPS} step limit"


# --------------------------------------------------------- runner + checker
def test_scenario(scenario, agent, broken):
    runs = []
    for attempt in range(1, REPEATS + 1):
        phone = FakePhone(broken)                    # fresh phone each time (= reset)
        says_ok, msg = agent.run(scenario, phone, attempt)
        real = phone.read_setting(scenario["setting"])   # THE CHECKER: look at the phone itself
        runs.append({"agent_says": says_ok, "checker_read": real,
                     "passed": real == scenario["expected"]})

    # Can't tell: the checker could not read anything. Never counts as a pass.
    if all(r["checker_read"] is None for r in runs):
        return runs, "CAN'T TELL", "the phone can't show this, so no verdict"

    if all(r["passed"] for r in runs):
        return runs, "PASS", "the phone really changed every time"

    # Something failed. Direct path: do the action ourselves, without any agent.
    phone = FakePhone(broken)
    phone.change_setting(scenario["setting"], scenario["expected"])
    direct_works = phone.read_setting(scenario["setting"]) == scenario["expected"]

    if not any(r["passed"] for r in runs) and not direct_works:
        return runs, "PRODUCT BUG", "failed every time and even the direct path failed"
    return runs, "AGENT MISTAKE", "the phone can do it (direct path works), the agent didn't"


def report(agent_name, agent, broken):
    print(f"\n=== agent: {agent_name}   broken settings: {', '.join(broken) or 'none'} ===")
    for sc in SCENARIOS:
        runs, label, why = test_scenario(sc, agent, broken)
        says = "".join("Y" if r["agent_says"] else "N" for r in runs)
        real = ", ".join(str(r["checker_read"]) for r in runs)
        print(f"- {sc['task']:<34} agent said ok: {says}   checker read: {real}")
        print(f"  -> {label}: {why}")


AGENTS = {"honest": HonestAgent, "liar": LiarAgent, "flaky": FlakyAgent, "claude": ClaudeAgent}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--agent", choices=AGENTS, help="leave out to run the tour")
    p.add_argument("--broken", nargs="*", default=[], help="settings that are broken, e.g. wifi")
    a = p.parse_args()

    if a.agent or a.broken:  # --broken on its own uses the honest agent
        name = a.agent or "honest"
        try:
            report(name, AGENTS[name](), a.broken)
        except Exception as e:  # e.g. a wrong API key or no credits, show it in one line
            if type(e).__module__.startswith("anthropic"):
                raise SystemExit(f"Claude API error: {e}")
            raise
    else:  # the tour: one situation for every label
        report("honest", HonestAgent(), [])          # everything works -> PASS
        report("honest", HonestAgent(), ["wifi"])    # phone is broken -> PRODUCT BUG
        report("liar", LiarAgent(), [])              # agent lies      -> AGENT MISTAKE
        report("flaky", FlakyAgent(), [])            # works 1 of 3    -> AGENT MISTAKE
