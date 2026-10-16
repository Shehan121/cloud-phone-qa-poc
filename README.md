# QA check for Mobilerun

This repo goes with my design doc "QA Agent for Mobilerun". The main idea is simple , the agent does a task on a phone and then a separate checker looks at the phone itself. The agent never grades its own work.

Everything is in simple_demo. One Python file , no cloud phone , no install. It shows the whole idea in a few seconds.

```bash
cd simple_demo
python demo.py
```

## The rules

- the agent runs every task 3 times
- the checker reads the real result from the phone , not what the agent says
- if it failed , the runner does the action itself without the agent (direct path)
- fails every time and the direct path fails too : product bug
- the direct path works : agent mistake
- the checker can't read the result : can't tell , and that is never a pass
