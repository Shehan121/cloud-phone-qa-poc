"""
Tiny local stand-in for the Mobilerun API, only for testing qa_check.py offline.
It implements just the endpoints the script calls, with the same paths and
JSON field names as the official SDK (mobilerun-sdk 6.0.0). It is NOT Mobilerun.

Modes (MOCK_MODE env var):
  agent_ok        the agent changes the time zone and says succeeded
  agent_lies      the agent says succeeded but changes nothing
  agent_flaky     the agent only succeeds on the 2nd run
  platform_broken setting the time zone never sticks, not even directly
  env_429         POST /tasks answers 429 RESOURCE_EXHAUSTED
"""
import json, os, re, itertools
from http.server import BaseHTTPRequestHandler, HTTPServer

MODE = os.environ.get("MOCK_MODE", "agent_ok")
STATE = {"tz": "America/New_York", "tasks": {}}
counter = itertools.count(1)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body=None):
        data = b"" if body is None else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = self.path.split("?")[0]
        if re.fullmatch(r"/devices/[^/]+", p):
            return self.send(200, {"id": "dev1", "state": "ready", "stateMessage": ""})
        if re.fullmatch(r"/devices/[^/]+/capabilities", p):
            caps = {k: True for k in ["accessibility", "agent", "apps", "browser", "clipboard", "files", "time", "language"]}
            return self.send(200, {"capabilities": caps, "deviceType": "android_cloud_phone"})
        if re.fullmatch(r"/devices/[^/]+/timezone", p):
            return self.send(200, {"timezone": STATE["tz"]})
        m = re.fullmatch(r"/tasks/([^/]+)/status", p)
        if m:
            t = STATE["tasks"][m.group(1)]
            return self.send(200, {"status": "completed", "succeeded": t["succeeded"], "steps": 7, "message": "done"})
        m = re.fullmatch(r"/tasks/([^/]+)", p)
        if m:
            return self.send(200, {"task": {"id": m.group(1), "creditsUsed": 3.5, "status": "completed"}})
        self.send(404, {"error": "not mocked: " + p})

    def do_POST(self):
        p = self.path.split("?")[0]
        b = self.body()
        if re.fullmatch(r"/devices/[^/]+/timezone", p):
            if MODE != "platform_broken":
                STATE["tz"] = b["timezone"]
            return self.send(204)
        if p == "/tasks":
            if MODE == "env_429":
                return self.send(429, {"code": "RESOURCE_EXHAUSTED"})
            n = next(counter)
            tid = f"task_{n}"
            change = MODE == "agent_ok" or (MODE == "agent_flaky" and n == 2)
            if change and MODE != "platform_broken":
                STATE["tz"] = "Asia/Tokyo"
            STATE["tasks"][tid] = {"succeeded": True}
            return self.send(201, {"id": tid, "status": "queued", "streamUrl": None})
        self.send(404, {"error": "not mocked: " + p})


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(os.environ.get("MOCK_PORT", "4011"))), H).serve_forever()
