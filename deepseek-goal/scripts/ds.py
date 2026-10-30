#!/usr/bin/env python3
"""DeepSeek Flash subagents through opencode. The model is fixed: no other can be requested.

  ds.py probe                          one short call: ok / quota / error
  ds.py run <dir> <task.md> [--timeout 2400] [--report <path>] [--agent <id>]
  ds.py status <session-id>            outcome, cost, pending permissions or forms
  ds.py final  <session-id>            last text of the subagent

`--agent`: an opencode agent (for example `revisor`, read-only); the model is still Flash.
`--report`: file where the task asked the subagent to write its report. It is printed at the
end if it exists: the model's last message sometimes arrives empty.

Env: OC_SERVER=http://host:port for another `opencode serve`.
Exit code of `run`: 0 finished, 2 timeout, 3 quota, 4 stuck on a permission or form.
"""
from __future__ import annotations
import json, os, subprocess, sys, time, tempfile
from pathlib import Path

# Probes run outside any repo: in the cwd they left an empty .oc-probe/ in every project.
PROBE_DIR = Path(tempfile.gettempdir()) / "oc-probe"

# Single source of the model. The user chose it and pays for the API: it is not changed from here.
MODEL = ("deepseek", "deepseek-flash")


def api(method, path, body=None, timeout=60):
    args = ["opencode", "api", method, path]
    if os.environ.get("OC_SERVER"):
        args[2:2] = ["--server", os.environ["OC_SERVER"]]
    if body is not None:
        args += ["-d", json.dumps(body)]
    p = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{method} {path}: {(p.stderr or p.stdout).strip()[:300]}")
    out = p.stdout.strip()
    try:
        j = json.loads(out) if out else {}
    except json.JSONDecodeError:
        return out
    return j.get("data", j) if isinstance(j, dict) else j


def new_session(title, directory, agent=None):
    Path(directory).mkdir(parents=True, exist_ok=True)
    body = {"title": title, "location": {"directory": str(Path(directory).resolve())},
            "model": {"providerID": MODEL[0], "id": MODEL[1]}}
    if agent:
        body["agent"] = agent
    return api("POST", "/api/session", body)["id"]


def children(sid):
    out, todo = [], [sid]
    while todo:
        for k in api("GET", f"/api/session?parentID={todo.pop()}&limit=200") or []:
            out.append(k["id"]); todo.append(k["id"])
    return out


def as_list(x):
    return [i for i in x if isinstance(i, dict)] if isinstance(x, list) else []


def recent_messages(sid):
    # `opencode api` output is cut at about 256 KB when read through a pipe, and a few turns of
    # long reasoning exceed it: the JSON breaks and the report looked empty. The API returns newest
    # first, so ask for fewer messages until the answer parses.
    for n in (8, 3, 1):
        msgs = api("GET", f"/api/session/{sid}/message?limit={n}")
        if isinstance(msgs, list):
            return as_list(msgs)
    return []


def final_text(sid):
    for m in recent_messages(sid):
        texts = [c["text"] for c in as_list(m.get("content")) if c.get("type") == "text" and c.get("text", "").strip()]
        if texts:
            return texts[-1]
    return ""


def error_of(sid):
    for m in recent_messages(sid)[:3]:
        if e := m.get("error"):
            return json.dumps(e)[:400]
    return None


def pending(tree):
    perms = [(s, p.get("action"), (p.get("resources") or [""])[:1]) for s in tree
             for p in as_list(api("GET", f"/api/session/{s}/permission"))]
    forms = [(s, f.get("id")) for s in tree for f in as_list(api("GET", f"/api/session/{s}/form"))]
    return perms, forms


def settled(s):
    t = s.get("time", {})
    return bool(s.get("outcome") and t.get("idle") and t["idle"] >= t.get("updated", 0))


def cmd_probe():
    sid = new_session("ds-probe", PROBE_DIR)
    api("POST", f"/api/session/{sid}/prompt", {"text": "Reply with the single word OK."})
    t0 = time.time()
    while time.time() - t0 < 90 and not settled(api("GET", f"/api/session/{sid}")):
        time.sleep(3)
    err = error_of(sid)
    state = "quota" if err and "quota" in err else ("error " + err if err else ("ok" if "OK" in final_text(sid) else "no-answer"))
    print(f"{'/'.join(MODEL)}: {state} ({round(time.time() - t0)}s)", flush=True)


def cmd_run(directory, task, timeout, report, agent=None):
    sid = new_session(f"ds-{Path(task).stem}", directory, agent)
    print("session", sid, "model", "/".join(MODEL), flush=True)
    api("POST", f"/api/session/{sid}/prompt", {"text": Path(task).read_text()})
    t0, last, code = time.time(), None, 2
    while time.time() - t0 < timeout:
        time.sleep(15)
        if settled(api("GET", f"/api/session/{sid}")):
            code = 0; break
        err = error_of(sid)
        if err and "quota" in err:
            print("QUOTA", err, flush=True); code = 3; break
        p = pending([sid] + children(sid))
        if (p[0] or p[1]) and p == last:
            print("STUCK", p, flush=True); code = 4; break
        last = p
    s = api("GET", f"/api/session/{sid}")
    print("outcome", s.get("outcome"), "secs", round(time.time() - t0), "cost", s.get("cost"))
    if err := error_of(sid):
        print("ERROR", err)
    print("FINAL:", final_text(sid)[-3000:] or "(empty)")
    if report and Path(report).is_file():
        print("REPORT:", Path(report).read_text()[-6000:])
    if (Path(directory) / ".git").exists() or subprocess.run(["git", "-C", str(directory), "rev-parse"], capture_output=True).returncode == 0:
        print(subprocess.run(["git", "-C", str(directory), "status", "--short"], capture_output=True, text=True).stdout)
    sys.exit(code)


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    if a[0] == "probe":
        cmd_probe()
    elif a[0] == "run" and len(a) >= 3:
        cmd_run(a[1], a[2], int(opt("--timeout", 2400)), opt("--report"), opt("--agent"))
    elif a[0] == "status":
        s = api("GET", f"/api/session/{a[1]}")
        tree = [a[1]] + children(a[1])
        print(json.dumps({"outcome": s.get("outcome"), "cost": s.get("cost"), "settled": settled(s),
                          "subsessions": len(tree) - 1, "error": error_of(a[1]), "pending": pending(tree)}, indent=1))
    elif a[0] == "final":
        print(final_text(a[1]))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
