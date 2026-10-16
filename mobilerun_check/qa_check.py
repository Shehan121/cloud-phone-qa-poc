"""
QA check for Mobilerun: one scenario, end to end.

Scenario: "change the phone's time zone to Tokyo".
The Mobilerun agent does the task on a cloud phone. Then this script reads the
real time zone through the Mobilerun API and compares it with the expected
value. The agent's own `succeeded` is never trusted as the verdict.

Flow (same as the design doc):
  1. preflight  : device is ready and has the `agent` and `time` capabilities
  2. calibrate  : set the expected and the start time zone directly and read both back,
                  so the checker is proven on a known good and a known bad state
                  (and the start state is known before every run)
  3. run 3x     : POST /tasks, poll GET /tasks/{id}/status, read GET /devices/{id}/timezone
  4. direct path: if anything failed, set the time zone directly through the API
                  (no agent) and read it back. Works -> agent mistake, fails -> product bug
  5. restore    : put the original time zone back
  6. report     : verdict + label + evidence (task ids, steps, credits) as JSON

Usage:
  pip install mobilerun-sdk==6.0.0
  export MOBILERUN_CLOUD_API_KEY=dr_sk_...
  python qa_check.py --device-id <id of a ready cloud phone> --yes

Cost: each run is at most --max-steps steps at about 0.5 credits per step
(docs.mobilerun.ai/credits), so 3 repeats x 30 steps is at most ~45 credits.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from typing import Optional

from mobilerun_sdk import Mobilerun, APIStatusError, APIConnectionError

TERMINAL = {"completed", "failed", "cancelled"}          # docs.mobilerun.ai/tasks
ENVIRONMENT_HTTP = {402, 422, 429}                         # docs.mobilerun.ai/devices
CREDITS_PER_STEP = 0.5                                     # docs.mobilerun.ai/credits

SCENARIO = {
    "id": "settings-timezone-tokyo",
    "task": (
        "Open the Settings app and change the phone's time zone to Tokyo, Japan (GMT+9). "
        "If automatic time zone is on, turn it off first."
    ),
    "expected_timezone": "Asia/Tokyo",
    "baseline_timezone": "Europe/Berlin",
}


@dataclass
class Attempt:
    repeat: int
    task_id: Optional[str] = None
    status: Optional[str] = None
    agent_succeeded: Optional[bool] = None
    termination_reason: Optional[str] = None
    steps: Optional[int] = None
    credits_used: Optional[float] = None
    read_value: Optional[str] = None
    result: str = "CANT_TELL"          # PASS | FAIL | CANT_TELL
    note: str = ""


@dataclass
class Report:
    scenario: str
    device_id: str
    expected: str
    verdict: str = "CANT_TELL"          # PASS | FAIL | CANT_TELL
    label: str = ""                     # product_bug | agent_mistake | environment | cant_tell | ""
    direct_path: Optional[str] = None   # works | fails | not_run
    agent_wrong_about_itself: int = 0   # agent said succeeded but the check failed (or the reverse)
    attempts: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def read_timezone(client: Mobilerun, device_id: str) -> Optional[str]:
    """The checker. Reads the real state, returns None if it can't."""
    try:
        return client.devices.timezone.get(device_id).timezone
    except (APIStatusError, APIConnectionError):
        return None


def set_timezone(client: Mobilerun, device_id: str, tz: str) -> bool:
    try:
        client.devices.timezone.set(device_id, timezone=tz)
        return True
    except (APIStatusError, APIConnectionError):
        return False


def preflight(client: Mobilerun, device_id: str, report: Report) -> bool:
    try:
        info = client.devices.retrieve(device_id)
        if info.state != "ready":
            report.notes.append(f"device state is '{info.state}', waiting for ready")
            client.devices.wait_ready(device_id)
        caps = client.devices.retrieve_capabilities(device_id).capabilities
    except APIStatusError as e:
        report.label = "environment" if e.status_code in ENVIRONMENT_HTTP else "cant_tell"
        report.notes.append(f"preflight failed: HTTP {e.status_code}")
        return False
    except APIConnectionError as e:
        report.label = "cant_tell"
        report.notes.append(f"preflight failed: {e}")
        return False
    if not (caps.agent and caps.time):
        report.label = "cant_tell"
        report.notes.append("device lacks the 'agent' or 'time' capability, scenario not applicable")
        return False
    return True


def calibrate(client: Mobilerun, device_id: str, report: Report) -> bool:
    """Test the checker on a known-good and a known-bad state before trusting it.
    Sets both values directly through the API (no agent) and reads them back."""
    for tz in (SCENARIO["expected_timezone"], SCENARIO["baseline_timezone"]):
        set_ok = set_timezone(client, device_id, tz)
        value = read_timezone(client, device_id)
        if value is None:
            report.verdict, report.label = "CANT_TELL", "cant_tell"
            report.notes.append("checker could not read the time zone, nothing is trusted")
            return False
        if not set_ok or value != tz:
            # the platform itself can't change the time zone, not even without the agent
            report.verdict, report.label, report.direct_path = "FAIL", "product_bug", "fails"
            report.notes.append(f"direct set to {tz} did not stick (read back {value})")
            return False
    return True


def run_once(client: Mobilerun, device_id: str, n: int, args) -> Attempt:
    a = Attempt(repeat=n)

    # known start state, and prove the checker can read it
    if not set_timezone(client, device_id, SCENARIO["baseline_timezone"]) or \
            read_timezone(client, device_id) != SCENARIO["baseline_timezone"]:
        a.note = "could not set or read the baseline time zone"
        return a  # CANT_TELL

    try:
        started = client.tasks.run(
            device_id=device_id,
            task=SCENARIO["task"],
            max_steps=args.max_steps,
            execution_timeout=args.execution_timeout,
        )
    except APIStatusError as e:
        a.result, a.note = "CANT_TELL", f"task not started: HTTP {e.status_code}"
        a.status = "environment" if e.status_code in ENVIRONMENT_HTTP else "error"
        return a
    a.task_id = started.id

    deadline = time.monotonic() + args.execution_timeout + 300   # queue + contention margin
    status = None
    while time.monotonic() < deadline:
        status = client.tasks.get_status(a.task_id)
        if status.status in TERMINAL:
            break
        time.sleep(args.poll_seconds)
    else:
        a.note = "task did not reach a terminal state in time"
        return a  # CANT_TELL

    a.status = status.status
    a.agent_succeeded = status.succeeded
    a.steps = status.steps
    if status.execution is not None:
        a.termination_reason = status.execution.termination_reason
    try:
        a.credits_used = client.tasks.retrieve(a.task_id).task.credits_used
    except APIStatusError:
        pass

    if a.termination_reason == "worker_lost":
        a.note = "worker_lost: environment, not counted against the product"
        return a  # CANT_TELL

    # the checker decides, not the agent
    a.read_value = read_timezone(client, device_id)
    if a.read_value is None:
        a.note = "checker could not read the time zone"
        return a  # CANT_TELL
    a.result = "PASS" if a.read_value == SCENARIO["expected_timezone"] else "FAIL"
    return a


def direct_path(client: Mobilerun, device_id: str) -> str:
    """Do the same change without the agent. If even this fails, the platform is broken."""
    set_timezone(client, device_id, SCENARIO["baseline_timezone"])
    ok = set_timezone(client, device_id, SCENARIO["expected_timezone"])
    return "works" if ok and read_timezone(client, device_id) == SCENARIO["expected_timezone"] else "fails"


def triage(report: Report) -> None:
    results = [a.result for a in report.attempts]
    if not results or all(r == "CANT_TELL" for r in results):
        report.verdict = "CANT_TELL"
        report.label = report.label or (
            "environment" if any(a.status == "environment" or a.termination_reason == "worker_lost"
                                 for a in report.attempts) else "cant_tell")
        return
    if all(r == "PASS" for r in results):
        report.verdict, report.label = "PASS", ""
        return
    if "FAIL" not in results:                    # mix of PASS and CANT_TELL
        report.verdict, report.label = "CANT_TELL", "cant_tell"
        return
    report.verdict = "FAIL"
    if report.direct_path == "fails":
        report.label = "product_bug"            # nobody can make it work
    else:
        report.label = "agent_mistake"          # platform works, the agent did not


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--device-id", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--execution-timeout", type=int, default=600, help="seconds, 1 to 2700")
    p.add_argument("--poll-seconds", type=float, default=5.0)
    p.add_argument("--yes", action="store_true", help="confirm that this spends real credits")
    args = p.parse_args()

    max_credits = args.repeats * args.max_steps * CREDITS_PER_STEP
    if not args.yes:
        print(f"This runs {args.repeats} real tasks and can use up to ~{max_credits:.0f} credits. "
              f"Add --yes to continue.")
        return 2

    client = Mobilerun()   # reads MOBILERUN_CLOUD_API_KEY
    report = Report(scenario=SCENARIO["id"], device_id=args.device_id, expected=SCENARIO["expected_timezone"])

    original = read_timezone(client, args.device_id)
    try:
        if preflight(client, args.device_id, report) and calibrate(client, args.device_id, report):
            for n in range(1, args.repeats + 1):
                a = run_once(client, args.device_id, n, args)
                report.attempts.append(a)
                if a.agent_succeeded is not None and a.result in ("PASS", "FAIL") and \
                        a.agent_succeeded != (a.result == "PASS"):
                    report.agent_wrong_about_itself += 1
            if any(a.result == "FAIL" for a in report.attempts):
                report.direct_path = direct_path(client, args.device_id)
            else:
                report.direct_path = "not_run"
            triage(report)
    finally:
        if original:
            set_timezone(client, args.device_id, original)

    out = asdict(report)
    print(json.dumps(out, indent=2))
    print(f"\nVERDICT: {report.verdict}" + (f"  LABEL: {report.label}" if report.label else ""))
    return 0 if report.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
