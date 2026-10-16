# Mobilerun check

The real version of the simple demo for one scenario : change the phone's time zone to Tokyo. I picked it because the result can be read exactly with GET /devices/{id}/timezone and it is easy to undo.

## What it does

1. checks the phone is ready
2. sets the time zone directly once to make sure the checker can read it
3. sends the task to the Mobilerun agent 3 times and reads the time zone after each run
4. if a run failed it sets the time zone itself (direct path) to tell a product bug from an agent mistake
5. puts the old time zone back and prints the result as JSON

## Run it

```bash
pip install -r requirements.txt
export MOBILERUN_CLOUD_API_KEY=dr_sk_...
python qa_check.py --device-id <id of a ready cloud phone> --yes
```

Without --yes it only shows how many credits it could use. With 3 repeats and 30 steps max that is at most about 45 credits.

## Tested so far

Not on a real phone yet. I tested it against mock/mock_mobilerun.py , a small local fake of the Mobilerun API with the same paths and fields as the official SDK.

| mock mode | result |
|---|---|
| agent_ok | PASS |
| agent_lies | FAIL , agent mistake |
| agent_flaky | FAIL , agent mistake |
| platform_broken | FAIL , product bug |
| env_429 | CAN'T TELL , environment |

```bash
MOCK_MODE=agent_flaky python mock/mock_mobilerun.py &
MOBILERUN_BASE_URL=http://127.0.0.1:4011 MOBILERUN_CLOUD_API_KEY=test python qa_check.py --device-id dev1 --yes --poll-seconds 0.1
```

sample_output_mock_agent_flaky.txt is the output of that run. scenarios.yaml has more example scenarios from the design doc.
