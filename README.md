# Mobilerun QA check (proof of concept)

This is a small proof of concept for my design doc "QA Agent for Mobilerun". It runs one scenario end to end the way the design describes it.

The Mobilerun agent does a task on a cloud phone and then a separate checker reads the real state of the phone through the Mobilerun API and compares it with the expected value. The agent's own `succeeded` is recorded but never used as the verdict.

Scenario : change the phone's time zone to Tokyo. I picked this one because the result can be read exactly through `GET /devices/{id}/timezone` and it is safe to undo. (Turning Wi-Fi off on a cloud phone could cut its connection , so Wi-Fi is only used as an example in the doc.)

## What it does

1. Preflight : the device is `ready` and has the `agent` and `time` capabilities.
2. Calibrate the checker : set Tokyo and the start time zone directly through the API and read both back. If the checker can't read it the result is can't tell. If even a direct set doesn't stick it is a product bug.
3. Run the task 3 times through `POST /tasks` , poll `GET /tasks/{id}/status` until it is `completed`, `failed` or `cancelled` , then read the time zone.
4. If any run failed , try the direct path (set the time zone without the agent). Works → agent mistake , fails → product bug.
5. Put the original time zone back.
6. Print a JSON report with the verdict, the label and the evidence (task ids, steps, credits, termination reason, how often the agent was wrong about itself).

Verdicts : `PASS`, `FAIL`, `CANT_TELL`. Labels : `product_bug`, `agent_mistake`, `environment`, `cant_tell`. Can't tell never counts as a pass.

## Run it

```bash
pip install mobilerun-sdk==6.0.0
export MOBILERUN_CLOUD_API_KEY=dr_sk_...
python qa_check.py --device-id <id of a ready cloud phone> --yes
```

Without `--yes` it only prints how many credits it could use. With the defaults (3 repeats , 30 steps max) that is at most about 45 credits (about 0.5 credits per step).

## Tested so far

I haven't run this against a real Mobilerun phone yet. I tested it against `mock/mock_mobilerun.py` , a small local stand-in that uses the same paths and field names as the official SDK. It is not Mobilerun. All five cases give the expected result :

| mock mode | what happens | result |
|---|---|---|
| agent_ok | agent changes the time zone | PASS |
| agent_lies | agent says succeeded , nothing changes | FAIL , agent_mistake |
| agent_flaky | agent only works on 1 of 3 runs | FAIL , agent_mistake |
| platform_broken | the time zone can't be set at all | FAIL , product_bug |
| env_429 | `POST /tasks` returns 429 | CANT_TELL , environment |

```bash
MOCK_MODE=agent_flaky python mock/mock_mobilerun.py &
MOBILERUN_BASE_URL=http://127.0.0.1:4011 MOBILERUN_CLOUD_API_KEY=test python qa_check.py --device-id dev1 --yes --poll-seconds 0.1
```

`sample_output_mock_agent_flaky.txt` is the output of that run.

## Files

- `qa_check.py` : the check
- `scenarios.yaml` : 11 example scenarios from the design doc with what is checked and how
- `mock/mock_mobilerun.py` : local mock for testing without credits
