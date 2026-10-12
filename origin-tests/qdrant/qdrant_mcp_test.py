import json
import os
import subprocess
import sys

# .mcp.json이 있는 폴더에서 실행한다 (예: qdrant_rag_test)
PROJECT = os.getcwd()

cfg = json.load(open(os.path.join(PROJECT, ".mcp.json")))["mcpServers"]["qdrant"]
env = {**os.environ, **cfg.get("env", {})}
proc = subprocess.Popen(
    [cfg["command"], *cfg["args"]],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    text=True,
    bufsize=1,
)

next_id = 0


def rpc(method, params=None, notify=False):
    global next_id
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if not notify:
        next_id += 1
        msg["id"] = next_id
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    if notify:
        return None
    while True:
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read()
            sys.exit(f"서버 응답 없음 (stderr):\n{err[-2000:]}")
        resp = json.loads(line)
        if resp.get("id") == next_id:
            return resp


init = rpc(
    "initialize",
    {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "qdrant-test", "version": "0.1"},
    },
)
print("INITIALIZE:", "OK" if "result" in init else init)
rpc("notifications/initialized", notify=True)

tools = rpc("tools/list")
names = [t["name"] for t in tools["result"]["tools"]]
print("TOOLS:", names)

store = rpc(
    "tools/call",
    {
        "name": "qdrant-store",
        "arguments": {
            "information": "연차는 입사 1년 후 15일이 발생하며, 사용 신청은 최소 3일 전에 해야 한다.",
            "metadata": {"source": "test-policy"},
        },
    },
)
print("STORE:", json.dumps(store.get("result", store), ensure_ascii=False)[:300])

find = rpc("tools/call", {"name": "qdrant-find", "arguments": {"query": "연차 휴가 신청 기간"}})
print("FIND:", json.dumps(find.get("result", find), ensure_ascii=False)[:600])

proc.terminate()
