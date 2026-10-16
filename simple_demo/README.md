# Simple demo

The smallest version of the idea. The phone is fake (a Python object with Wi-Fi , dark theme and time zone) so it runs on any laptop.

The agent is borrowed , I didn't build one. It is either Claude or one of three fake agents :

- honest : really does the task
- liar : says done but does nothing
- flaky : only works on the 2nd try

## Run it

```bash
python demo.py
```

It runs four situations one after another :

| situation | result |
|---|---|
| honest agent , working phone | PASS |
| honest agent , Wi-Fi broken on the phone | Wi-Fi is a PRODUCT BUG |
| liar agent | AGENT MISTAKE |
| flaky agent | AGENT MISTAKE |

The WhatsApp task is always CAN'T TELL because the fake phone has no way to show it.

You can also pick an agent and break a setting yourself :

```bash
python demo.py --agent liar
python demo.py --agent flaky --broken timezone
```

## With Claude as the agent

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python demo.py --agent claude --broken wifi
```

Claude gets three tools , look at the screen , change a setting and finish. Whatever Claude says at the end , the checker still reads the phone. So with Wi-Fi broken it is a product bug even if Claude says done.

## How it maps to Mobilerun

- fake phone : a Mobilerun cloud phone
- agent.run : POST /tasks to the Mobilerun agent
- read_setting : GET /devices/{id}/timezone or ui-state
- direct path : POST /devices/{id}/tap and the other direct device calls

## Results

Screenshots of the runs and a short explanation of each are in [RESULTS.md](RESULTS.md).
