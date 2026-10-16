# QA check for Mobilerun

This repo goes with my design doc "QA Agent for Mobilerun". The main idea is simple , the agent does a task on a phone and then a separate checker looks at the phone itself. The agent never grades its own work.

There are two folders.

## simple_demo

Start here. One Python file , no cloud phone , no install. It shows the whole idea in a few seconds.

```bash
cd simple_demo
python demo.py
```

## mobilerun_check

The same idea against the real Mobilerun API for one scenario (change the time zone to Tokyo). I only tested it against a small local mock , not a real phone yet.

```bash
cd mobilerun_check
pip install -r requirements.txt
export MOBILERUN_CLOUD_API_KEY=dr_sk_...
python qa_check.py --device-id <id of a ready cloud phone> --yes
```

## The rules

- the agent runs every task 3 times
- the checker reads the real result from the phone , not what the agent says
- if it failed , the runner does the action itself without the agent (direct path)
- fails every time and the direct path fails too : product bug
- the direct path works : agent mistake
- the checker can't read the result : can't tell , and that is never a pass
